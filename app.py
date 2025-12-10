from flask import Flask, render_template, send_file, jsonify, Response, stream_with_context, request
import boto3
from dotenv import load_dotenv
import os
from io import BytesIO
from collections import defaultdict
import zipfile
import logging
import json
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()
logger.info("Environment variables loaded")

endpoint = os.getenv("ENDPOINT_URL")
bucket = os.getenv("BUCKET_NAME")
key = os.getenv("ACCESS_KEY")
secret = os.getenv("SECRET_KEY")
title = os.getenv("APP_TITLE", "Bkash MINIO Browser")

logger.info(f"Connecting to S3 - Endpoint: {endpoint}, Bucket: {bucket}")

s3 = boto3.client(
    "s3",
    aws_access_key_id=key,
    aws_secret_access_key=secret,
    endpoint_url=endpoint,
    config=boto3.session.Config(s3={"addressing_style": "path"})
)

app = Flask(__name__)

# Global dictionary to track download tasks
download_tasks = {}


def format_size(size_bytes):
    """Convert bytes to human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def build_tree(objects):
    """Build a hierarchical tree structure from flat object keys with sizes"""
    logger.info(f"Building tree structure for {len(objects)} objects")
    tree = defaultdict(lambda: {"files": [], "folders": defaultdict(dict)})
    
    for obj in objects:
        obj_key = obj['Key']
        obj_size = obj['Size']
        logger.debug(f"Processing object: {obj_key} (size: {format_size(obj_size)})")
        parts = obj_key.split('/')
        current = tree
        
        # Navigate through folders
        for i, part in enumerate(parts[:-1]):
            if part not in current:
                current[part] = {"files": [], "folders": {}}
            current = current[part]["folders"]
        
        # Add file to the current level
        if parts[-1]:  # Not empty (trailing slash case)
            parent_path = '/'.join(parts[:-1]) if len(parts) > 1 else ''
            if len(parts) > 1:
                current = tree
                for part in parts[:-2]:
                    current = current[part]["folders"]
                if parts[-2] not in current:
                    current[parts[-2]] = {"files": [], "folders": {}}
                current[parts[-2]]["files"].append({'key': obj_key, 'size': obj_size})
            else:
                tree["_root_files"] = tree.get("_root_files", {"files": [], "folders": {}})
                tree["_root_files"]["files"].append({'key': obj_key, 'size': obj_size})
    
    logger.info("Tree structure built successfully")
    return tree

def render_tree(tree, prefix="", level=0, parent_path=""):
    """Recursively render the tree structure as HTML"""
    logger.debug(f"Rendering tree at level {level}, path: {parent_path}")
    html = "<ul>"
    
    # Handle root files
    if "_root_files" in tree:
        logger.debug(f"Found {len(tree['_root_files']['files'])} root files")
        for file_obj in tree["_root_files"]["files"]:
            file_key = file_obj['key']
            file_size = format_size(file_obj['size'])
            filename = os.path.basename(file_key)
            html += f'<li class="file"><a href="/download/{file_key}">{filename}</a><span class="file-size">({file_size})</span></li>'
    
    # Process folders
    for folder_name, content in sorted(tree.items()):
        if folder_name == "_root_files":
            continue
            
        folder_path = f"{parent_path}/{folder_name}" if parent_path else folder_name
        logger.debug(f"Processing folder: {folder_path}")
        folder_id = f"folder_{prefix}_{folder_name}_{level}".replace('/', '_').replace(' ', '_')
        dropdown_id = f"dropdown_{prefix}_{folder_name}_{level}".replace('/', '_').replace(' ', '_')
        
        html += f'<li class="folder">'
        html += f'<div class="folder-header">'
        html += f'<span class="folder-name" onclick="toggleFolder(\'{folder_id}\')">{folder_name}</span>'
        
        # Three-dot menu
        html += f'<div class="three-dot-menu">'
        html += f'<button class="three-dot-btn" onclick="toggleDropdown(\'{dropdown_id}\', event)">⋮</button>'
        html += f'<div id="{dropdown_id}" class="dropdown-menu">'
        html += f'<a class="dropdown-item" onclick="downloadFolder(\'{folder_path}\', event)">📥 Download</a>'
        html += f'<a class="dropdown-item" onclick="showFolderInfo(\'{folder_path}\', event)">ℹ️ Info</a>'
        html += f'</div>'
        html += f'</div>'
        
        html += f'</div>'
        html += f'<div id="{folder_id}" class="collapsible">'
        
        # Render files in this folder
        if "files" in content:
            logger.debug(f"Folder {folder_path} contains {len(content['files'])} files")
            html += "<ul>"
            for file_obj in sorted(content["files"], key=lambda x: x['key']):
                file_key = file_obj['key']
                file_size = format_size(file_obj['size'])
                filename = os.path.basename(file_key)
                html += f'<li class="file"><a href="/download/{file_key}">{filename}</a><span class="file-size">({file_size})</span></li>'
            html += "</ul>"
        
        # Recursively render subfolders
        if "folders" in content and content["folders"]:
            logger.debug(f"Folder {folder_path} contains {len(content['folders'])} subfolders")
            html += render_tree(content["folders"], f"{prefix}_{folder_name}", level + 1, folder_path)
        
        html += "</div>"
        html += "</li>"
    
    html += "</ul>"
    return html

@app.route("/")
def index():
    logger.info("Index route accessed")
    try:
        logger.info(f"Fetching objects from bucket: {bucket}")
        objs = s3.list_objects_v2(Bucket=bucket)
        contents = objs.get("Contents", [])
        logger.info(f"Found {len(contents)} objects in bucket")
        
        tree = build_tree(contents)
        tree_html = render_tree(tree)
        
        logger.info("Successfully rendered index page")
        return render_template('index.html', tree=tree_html, bucket=bucket, title=title)
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}", exc_info=True)
        return f"Error: {str(e)}", 500

@app.route("/download/<path:keyname>")
def download(keyname):
    logger.info(f"Download requested for file: {keyname}")
    try:
        logger.info(f"Fetching object from S3: {keyname}")
        file_obj = s3.get_object(Bucket=bucket, Key=keyname)
        data = file_obj['Body'].read()
        filename = os.path.basename(keyname)
        logger.info(f"Successfully downloaded file: {filename} (size: {len(data)} bytes)")
        return send_file(BytesIO(data), as_attachment=True, download_name=filename)
    except Exception as e:
        logger.error(f"Error downloading file {keyname}: {str(e)}", exc_info=True)
        return f"Error downloading file: {str(e)}", 500

@app.route("/folder-info/<path:folder_path>")
def folder_info(folder_path):
    logger.info(f"Folder info requested: {folder_path}")
    try:
        # Normalize folder path
        if not folder_path.endswith('/'):
            folder_path += '/'
        
        logger.info(f"Fetching info for folder: {folder_path}")
        
        # List all objects in the folder using pagination
        objects = []
        continuation_token = None
        
        while True:
            if continuation_token:
                response = s3.list_objects_v2(
                    Bucket=bucket, 
                    Prefix=folder_path,
                    ContinuationToken=continuation_token
                )
            else:
                response = s3.list_objects_v2(Bucket=bucket, Prefix=folder_path)
            
            page_objects = response.get('Contents', [])
            objects.extend(page_objects)
            
            if response.get('IsTruncated'):
                continuation_token = response.get('NextContinuationToken')
            else:
                break
        
        # Calculate statistics
        total_size = 0
        file_count = 0
        subfolders = set()
        
        for obj in objects:
            key = obj['Key']
            
            # Skip the folder itself
            if key == folder_path:
                continue
            
            # Count files and size
            total_size += obj['Size']
            
            # Get relative path
            relative_path = key[len(folder_path):]
            
            # Check if it's a direct file or in a subfolder
            if '/' in relative_path:
                # It's in a subfolder
                subfolder = relative_path.split('/')[0]
                subfolders.add(subfolder)
            else:
                # It's a direct file
                if relative_path:  # Not empty
                    file_count += 1
        
        # Total files includes all files recursively
        total_files = len(objects) if len(objects) > 0 else 0  # Exclude folder itself
        
        info = {
            'path': folder_path.rstrip('/'),
            'file_count': total_files,
            'total_size': format_size(total_size),
            'total_size_bytes': total_size,
            'subfolder_count': len(subfolders)
        }
        
        logger.info(f"Folder info for {folder_path}: {info}")
        return jsonify(info)
        
    except Exception as e:
        logger.error(f"Error getting folder info {folder_path}: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route("/download-folder-progress/<path:folder_path>")
def download_folder_progress(folder_path):
    """Stream progress updates for folder download"""
    task_id = request.args.get('task_id', 'unknown')
    
    def generate():
        try:
            # Normalize folder path
            if not folder_path.endswith('/'):
                folder_path_normalized = folder_path + '/'
            else:
                folder_path_normalized = folder_path
            
            logger.info(f"[{task_id}] Starting folder download with progress: {folder_path_normalized}")
            
            # List all objects in the folder using pagination
            objects = []
            continuation_token = None
            page_count = 0
            
            while True:
                page_count += 1
                if continuation_token:
                    response = s3.list_objects_v2(
                        Bucket=bucket, 
                        Prefix=folder_path_normalized,
                        ContinuationToken=continuation_token
                    )
                else:
                    response = s3.list_objects_v2(Bucket=bucket, Prefix=folder_path_normalized)
                
                page_objects = response.get('Contents', [])
                objects.extend(page_objects)
                
                if response.get('IsTruncated'):
                    continuation_token = response.get('NextContinuationToken')
                else:
                    break
            
            logger.info(f"[{task_id}] Total objects found: {len(objects)}")
            
            if len(objects) == 0:
                yield f"data: {json.dumps({'status': 'error', 'message': 'No files found in folder'})}\n\n"
                return
            
            # Initialize task state
            download_tasks[task_id] = {'cancelled': False, 'zip_buffer': None}
            
            # Create zip file
            zip_buffer = BytesIO()
            file_count = 0
            total_bytes = 0
            
            compression = zipfile.ZIP_STORED if len(objects) > 100 else zipfile.ZIP_DEFLATED
            
            with zipfile.ZipFile(zip_buffer, 'w', compression) as zip_file:
                for idx, obj in enumerate(objects, 1):
                    # Check if cancelled
                    if download_tasks.get(task_id, {}).get('cancelled', False):
                        logger.info(f"[{task_id}] Download cancelled by user")
                        yield f"data: {json.dumps({'status': 'cancelled'})}\n\n"
                        return
                    
                    key = obj['Key']
                    
                    if key == folder_path_normalized:
                        continue
                    
                    logger.info(f"Processing file {idx}/{len(objects)}: {key}")
                    
                    try:
                        file_obj = s3.get_object(Bucket=bucket, Key=key)
                        file_data = file_obj['Body'].read()
                        
                        relative_path = key[len(folder_path_normalized):]
                        if relative_path:
                            zip_file.writestr(relative_path, file_data)
                            file_count += 1
                            total_bytes += len(file_data)
                            
                            # Send progress update
                            yield f"data: {json.dumps({'status': 'progress', 'current': file_count, 'total': len(objects)})}\n\n"
                    
                    except Exception as e:
                        logger.error(f"[{task_id}] Error processing file {key}: {str(e)}")
                        continue
            
            # Check if cancelled after completion
            if download_tasks.get(task_id, {}).get('cancelled', False):
                logger.info(f"[{task_id}] Download cancelled after zip creation")
                yield f"data: {json.dumps({'status': 'cancelled'})}\n\n"
                return
            
            zip_buffer.seek(0)
            
            # Store zip buffer in task
            download_tasks[task_id]['zip_buffer'] = zip_buffer
            download_tasks[task_id]['folder_name'] = os.path.basename(folder_path.rstrip('/'))
            
            logger.info(f"[{task_id}] Zip file created successfully with {file_count} files")
            
            # Send completion
            yield f"data: {json.dumps({'status': 'complete', 'file_count': file_count})}\n\n"
            
        except Exception as e:
            logger.error(f"[{task_id}] Error in download progress: {str(e)}", exc_info=True)
            yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route("/get-zip/<task_id>")
def get_zip(task_id):
    """Download the generated zip file"""
    logger.info(f"[{task_id}] Zip download requested")
    
    if task_id not in download_tasks:
        return "Download not found or expired", 404
    
    task = download_tasks[task_id]
    zip_buffer = task.get('zip_buffer')
    folder_name = task.get('folder_name', 'download')
    
    if not zip_buffer:
        return "Download not ready", 404
    
    # Create a copy of the buffer for sending
    zip_data = BytesIO(zip_buffer.getvalue())
    zip_filename = f"{folder_name}.zip"
    
    # Clean up task after a delay (in a background thread)
    def cleanup():
        import time
        time.sleep(60)  # Keep for 1 minute
        if task_id in download_tasks:
            del download_tasks[task_id]
            logger.info(f"[{task_id}] Task cleaned up")
    
    threading.Thread(target=cleanup, daemon=True).start()
    
    return send_file(zip_data, as_attachment=True, download_name=zip_filename, mimetype='application/zip')

@app.route("/cancel-download/<task_id>", methods=['POST'])
def cancel_download(task_id):
    """Cancel an ongoing download"""
    logger.info(f"[{task_id}] Cancel requested")
    
    if task_id in download_tasks:
        download_tasks[task_id]['cancelled'] = True
        return jsonify({'status': 'cancelled'})
    else:
        return jsonify({'status': 'not_found'}), 404

@app.route("/download-folder/<path:folder_path>")
def download_folder(folder_path):
    """Legacy direct download endpoint - kept for compatibility"""
    logger.info(f"Folder download requested: {folder_path}")
    try:
        # Normalize folder path
        if not folder_path.endswith('/'):
            folder_path += '/'
        
        logger.info(f"Listing objects in folder: {folder_path}")
        
        # List all objects in the folder using pagination for large folders
        objects = []
        continuation_token = None
        page_count = 0
        
        while True:
            page_count += 1
            logger.info(f"Fetching page {page_count} for folder listing")
            
            if continuation_token:
                response = s3.list_objects_v2(
                    Bucket=bucket, 
                    Prefix=folder_path,
                    ContinuationToken=continuation_token
                )
            else:
                response = s3.list_objects_v2(Bucket=bucket, Prefix=folder_path)
            
            page_objects = response.get('Contents', [])
            objects.extend(page_objects)
            logger.info(f"Page {page_count}: Found {len(page_objects)} objects (Total so far: {len(objects)})")
            
            # Check if there are more pages
            if response.get('IsTruncated'):
                continuation_token = response.get('NextContinuationToken')
                logger.info(f"More pages available, continuing with token: {continuation_token[:20]}...")
            else:
                break
        
        logger.info(f"Total objects found in folder {folder_path}: {len(objects)}")
        
        if len(objects) == 0:
            logger.warning(f"No objects found in folder {folder_path}")
            return "No files found in this folder", 404
        
        # Create a zip file in memory with optimized settings
        logger.info("Creating zip file in memory")
        zip_buffer = BytesIO()
        file_count = 0
        total_bytes = 0
        
        # Use ZIP_STORED for faster processing on large folders (no compression)
        # Switch to ZIP_DEFLATED for smaller folders
        compression = zipfile.ZIP_STORED if len(objects) > 100 else zipfile.ZIP_DEFLATED
        logger.info(f"Using compression mode: {'STORED (no compression)' if compression == zipfile.ZIP_STORED else 'DEFLATED'}")
        
        with zipfile.ZipFile(zip_buffer, 'w', compression) as zip_file:
            for idx, obj in enumerate(objects, 1):
                key = obj['Key']
                
                # Skip if it's just the folder itself
                if key == folder_path:
                    continue
                
                # Log progress every 10 files or for first/last file
                if idx == 1 or idx % 10 == 0 or idx == len(objects):
                    logger.info(f"Processing file {idx}/{len(objects)}: {key}")
                else:
                    logger.debug(f"Processing file {idx}/{len(objects)}: {key}")
                
                try:
                    # Download the file from S3
                    file_obj = s3.get_object(Bucket=bucket, Key=key)
                    file_data = file_obj['Body'].read()
                    
                    # Add to zip with relative path
                    relative_path = key[len(folder_path):]
                    if relative_path:  # Only add if not empty
                        zip_file.writestr(relative_path, file_data)
                        file_count += 1
                        total_bytes += len(file_data)
                        
                        if idx % 10 == 0:
                            logger.info(f"Progress: {file_count} files added, {format_size(total_bytes)} total")
                        
                except Exception as e:
                    logger.error(f"Error processing file {key}: {str(e)}")
                    # Continue with other files even if one fails
                    continue
        
        zip_buffer.seek(0)
        zip_size = zip_buffer.getbuffer().nbytes
        
        # Get folder name for the zip file
        folder_name = os.path.basename(folder_path.rstrip('/'))
        zip_filename = f"{folder_name}.zip"
        
        logger.info(f"Successfully created zip file: {zip_filename}")
        logger.info(f"  Files: {file_count}")
        logger.info(f"  Uncompressed size: {format_size(total_bytes)}")
        logger.info(f"  Zip size: {format_size(zip_size)}")
        logger.info(f"  Compression ratio: {((1 - zip_size/total_bytes) * 100):.2f}%" if total_bytes > 0 else "  Compression ratio: N/A")
        
        return send_file(zip_buffer, as_attachment=True, download_name=zip_filename, mimetype='application/zip')
        
    except Exception as e:
        logger.error(f"Error downloading folder {folder_path}: {str(e)}", exc_info=True)
        return f"Error downloading folder: {str(e)}", 500

if __name__ == "__main__":
    logger.info("Starting Flask application on 0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, threaded=True)