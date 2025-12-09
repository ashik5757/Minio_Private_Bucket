# MinIO Private Bucket Browser

A Flask-based web application for browsing and downloading files from MinIO/S3 private buckets with a modern, responsive UI featuring dark/light theme support.

## Features

- 🗂️ **Hierarchical File Browser** - Navigate through folders with expandable/collapsible tree structure
- 📥 **File Downloads** - Download individual files directly from the browser
- 📦 **Folder Downloads** - Download entire folders as ZIP archives with real-time progress tracking
- ℹ️ **Folder Information** - View detailed statistics including file count, total size, and file type distribution
- 🌓 **Theme Toggle** - Switch between dark and light themes
- 📊 **Progress Tracking** - Real-time progress updates for folder downloads with cancellation support
- 🔒 **Private Bucket Access** - Secure access to private S3/MinIO buckets using credentials

## Prerequisites

- Python 3.11 or higher
- MinIO or AWS S3 bucket credentials
- Docker and Docker Compose (for containerized deployment)

## Project Structure

```
.
├── app.py                  # Main Flask application
├── templates/
│   └── index.html         # Frontend template with dark/light theme
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker image configuration
├── docker-compose.yml    # Docker Compose setup
├── .env.example          # Example environment variables
├── .env                  # Your environment variables (create this)
└── README.md             # This file
```

## Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
ACCESS_KEY=your_minio_access_key
SECRET_KEY=your_minio_secret_key
ENDPOINT_URL=https://your-minio-endpoint.com
BUCKET_NAME=your-bucket-name
APP_TITLE=Your App Title
```

You can use `.env.example` as a template:
```bash
cp .env.example .env
# Edit .env with your actual credentials
```

## Local Development Setup

### Step 1: Clone the Repository

```bash
git clone <your-repo-url>
cd Minio_Private_Bucket
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate

# On Windows:
# venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your MinIO/S3 credentials
nano .env  # or use your preferred editor
```

### Step 5: Run the Application

```bash
python app.py
```

The application will start on `http://localhost:5000`

### Step 6: Access the Application

Open your web browser and navigate to:
```
http://localhost:5000
```

## Docker Deployment

### Prerequisites
- Docker installed and running
- Docker Compose installed

### Step 1: Configure Environment Variables

```bash
# Create .env file with your credentials
cp .env.example .env
# Edit .env with your actual MinIO/S3 credentials
```

### Step 2: Build Docker Image

```bash
# Build the Docker image
docker-compose build
```

This command:
- Reads the `Dockerfile`
- Creates a Python 3.11 slim-based image
- Installs system dependencies (gcc)
- Installs Python packages from `requirements.txt`
- Copies application files into the image
- Configures the application to run on port 5000

### Step 3: Run with Docker Compose

```bash
# Start the application in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

### Step 4: Access the Application

The application will be available at:
```
http://localhost:5000
```

### Docker Commands Reference

```bash
# Build and start
docker-compose up -d --build

# View running containers
docker-compose ps

# View logs
docker-compose logs -f minio-browser

# Stop containers
docker-compose stop

# Stop and remove containers
docker-compose down

# Restart application
docker-compose restart

# Rebuild without cache
docker-compose build --no-cache
```

## Manual Docker Build (without Docker Compose)

If you prefer to use Docker directly without Docker Compose:

```bash
# Build the image
docker build -t minio-browser:latest .

# Run the container
docker run -d \
  -p 5000:5000 \
  --name minio-browser \
  --env-file .env \
  minio-browser:latest

# View logs
docker logs -f minio-browser

# Stop container
docker stop minio-browser

# Remove container
docker rm minio-browser
```

## Application Architecture

### Backend (app.py)
- **Flask Framework** - Handles HTTP requests and routing
- **boto3** - AWS SDK for Python, used to interact with MinIO/S3
- **Logging** - Comprehensive logging for debugging and monitoring
- **Streaming Downloads** - Efficient folder downloads with progress tracking
- **Tree Structure** - Builds hierarchical representation of bucket contents

### Frontend (templates/index.html)
- **Responsive Design** - Works on desktop and mobile devices
- **Theme System** - Dark/light theme with localStorage persistence
- **Real-time Updates** - Server-Sent Events (SSE) for download progress
- **Modal Dialogs** - Info and progress modals for better UX
- **Collapsible Folders** - Interactive tree navigation

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main page - displays file browser |
| `/download/<path:keyname>` | GET | Download a single file |
| `/folder-info/<path:folder_path>` | GET | Get folder statistics (JSON) |
| `/download-folder-progress/<path:folder_path>` | GET | Stream folder download progress (SSE) |
| `/get-zip/<task_id>` | GET | Download generated ZIP file |
| `/cancel-download/<task_id>` | POST | Cancel ongoing download |
| `/download-folder/<path:folder_path>` | GET | Legacy folder download endpoint |

## Features Explained

### File Browser
- Displays bucket contents in a hierarchical tree structure
- Folders are collapsible/expandable
- Shows file sizes in human-readable format (B, KB, MB, GB, TB)

### Folder Download
1. Click the three-dot menu (⋮) next to any folder
2. Select "📥 Download"
3. Monitor real-time progress in the modal
4. ZIP file downloads automatically when complete
5. Cancel anytime during the process

### Folder Information
1. Click the three-dot menu (⋮) next to any folder
2. Select "ℹ️ Info"
3. View statistics:
   - Total number of files
   - Total size
   - File type distribution

### Theme Toggle
- Click the theme button in the header to switch between dark and light modes
- Preference is saved in localStorage and persists across sessions

## Troubleshooting

### Connection Issues
```bash
# Check if MinIO/S3 endpoint is accessible
curl -I https://your-minio-endpoint.com

# Verify credentials in .env file
cat .env
```

### Docker Issues
```bash
# Check if container is running
docker-compose ps

# View container logs
docker-compose logs -f

# Restart container
docker-compose restart
```

### Port Already in Use
```bash
# Change port in docker-compose.yml
ports:
  - "5001:5000"  # Use port 5001 instead
```

### Permission Issues
```bash
# Ensure .env file has correct permissions
chmod 600 .env

# Check Docker permissions
sudo usermod -aG docker $USER
# Log out and log back in
```

## Development

### Enable Debug Mode

Edit `app.py`:
```python
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
```

### View Application Logs

The application uses Python's logging module. Logs include:
- Environment variable loading
- S3 connection details
- Object processing
- Download operations
- Error messages

## Security Considerations

- ✅ Never commit `.env` file to version control (included in `.gitignore`)
- ✅ Use environment variables for sensitive credentials
- ✅ Consider implementing authentication for production use
- ✅ Use HTTPS in production environments
- ✅ Regularly update dependencies for security patches

## Dependencies

- **Flask 3.0.0** - Web framework
- **boto3 1.34.0** - AWS SDK for Python
- **python-dotenv 1.0.0** - Environment variable management


**Note**: This application is designed for private bucket access. Ensure your credentials have appropriate read permissions for the specified bucket.
