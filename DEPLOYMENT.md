# Deployment Guide - MLB Pitch Predictor

Complete guide for deploying the MLB Pitch Predictor application to production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Backend Deployment](#backend-deployment)
   - [Render](#render)
   - [Railway](#railway)
   - [AWS EC2](#aws-ec2)
4. [Frontend Deployment](#frontend-deployment)
   - [Vercel](#vercel)
   - [Netlify](#netlify)
   - [GitHub Pages](#github-pages)
5. [Docker Deployment](#docker-deployment)
6. [Environment Configuration](#environment-configuration)
7. [Post-Deployment](#post-deployment)

---

## Prerequisites

- Git installed
- Python 3.8+ (for backend)
- Node.js 14+ (for frontend)
- Account on chosen hosting platform
- Domain name (optional)

---

## Local Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Server runs on `http://localhost:8000`

### Frontend

```bash
cd frontend
npm install
npm start
```

Application runs on `http://localhost:3000`

---

## Backend Deployment

### Option 1: Render (Recommended for beginners)

**Pros:** Free tier, automatic deploys, easy setup
**Cons:** Cold starts on free tier

#### Steps:

1. **Create account** at [render.com](https://render.com)

2. **Create new Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select the repository

3. **Configure service:**
   ```
   Name: mlb-pitch-predictor-api
   Environment: Python 3
   Region: Choose nearest
   Branch: main
   Root Directory: backend
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

4. **Set environment variables:**
   - Go to "Environment" tab
   - Add variables if needed

5. **Deploy:**
   - Click "Create Web Service"
   - Wait for deployment (5-10 minutes)
   - Copy the URL (e.g., `https://mlb-pitch-predictor-api.onrender.com`)

#### Health Check:
```bash
curl https://mlb-pitch-predictor-api.onrender.com/health
```

---

### Option 2: Railway

**Pros:** Modern interface, great DX, simple pricing
**Cons:** No free tier (but $5 credit)

#### Steps:

1. **Create account** at [railway.app](https://railway.app)

2. **New Project:**
   - Click "New Project" → "Deploy from GitHub repo"
   - Select repository

3. **Configure:**
   - Railway auto-detects Python
   - Set root directory: `backend`
   - Add start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

4. **Generate domain:**
   - Go to Settings → Generate Domain

5. **Deploy:**
   - Automatic on push to main branch

---

### Option 3: AWS EC2 (Advanced)

**Pros:** Full control, scalable
**Cons:** More complex setup, manual configuration

#### Steps:

1. **Launch EC2 Instance:**
   - Ubuntu Server 22.04 LTS
   - t2.micro (free tier eligible)
   - Configure security group: Allow HTTP (80), HTTPS (443), SSH (22)

2. **Connect via SSH:**
   ```bash
   ssh -i your-key.pem ubuntu@your-ec2-ip
   ```

3. **Install dependencies:**
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv nginx -y
   ```

4. **Clone repository:**
   ```bash
   git clone https://github.com/yourusername/mlb-pitch-predictor.git
   cd mlb-pitch-predictor/backend
   ```

5. **Setup virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

6. **Create systemd service:**
   ```bash
   sudo nano /etc/systemd/system/mlb-api.service
   ```

   ```ini
   [Unit]
   Description=MLB Pitch Predictor API
   After=network.target

   [Service]
   User=ubuntu
   WorkingDirectory=/home/ubuntu/mlb-pitch-predictor/backend
   Environment="PATH=/home/ubuntu/mlb-pitch-predictor/backend/venv/bin"
   ExecStart=/home/ubuntu/mlb-pitch-predictor/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

   [Install]
   WantedBy=multi-user.target
   ```

7. **Start service:**
   ```bash
   sudo systemctl start mlb-api
   sudo systemctl enable mlb-api
   ```

8. **Configure Nginx:**
   ```bash
   sudo nano /etc/nginx/sites-available/mlb-api
   ```

   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

   ```bash
   sudo ln -s /etc/nginx/sites-available/mlb-api /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

---

## Frontend Deployment

### Option 1: Vercel (Recommended)

**Pros:** Optimized for React, automatic deploys, free tier
**Cons:** Limited to static sites + serverless functions

#### Steps:

1. **Install Vercel CLI:**
   ```bash
   npm install -g vercel
   ```

2. **Login:**
   ```bash
   vercel login
   ```

3. **Deploy:**
   ```bash
   cd frontend
   vercel
   ```

4. **Configure:**
   - Follow prompts
   - Set root directory: `frontend`
   - Build command: `npm run build`
   - Output directory: `build`

5. **Set environment variables:**
   ```bash
   vercel env add REACT_APP_API_URL
   ```
   Enter your backend URL (e.g., `https://mlb-pitch-predictor-api.onrender.com`)

6. **Production deployment:**
   ```bash
   vercel --prod
   ```

#### Alternative: Vercel Dashboard

1. Go to [vercel.com](https://vercel.com)
2. Import GitHub repository
3. Set root directory: `frontend`
4. Add environment variable: `REACT_APP_API_URL`
5. Deploy

---

### Option 2: Netlify

**Pros:** Easy to use, continuous deployment
**Cons:** Similar to Vercel

#### Steps:

1. **Login** to [netlify.com](https://netlify.com)

2. **New site from Git:**
   - Click "Add new site" → "Import an existing project"
   - Connect to GitHub
   - Select repository

3. **Configure:**
   ```
   Base directory: frontend
   Build command: npm run build
   Publish directory: frontend/build
   ```

4. **Environment variables:**
   - Go to Site settings → Build & deploy → Environment
   - Add `REACT_APP_API_URL` with backend URL

5. **Deploy:**
   - Click "Deploy site"

#### Manual Deploy:

```bash
cd frontend
npm run build
npm install -g netlify-cli
netlify deploy --prod --dir=build
```

---

### Option 3: GitHub Pages

**Pros:** Free, simple
**Cons:** Static only, requires API CORS setup

#### Steps:

1. **Update package.json:**
   ```json
   {
     "homepage": "https://yourusername.github.io/mlb-pitch-predictor",
     "scripts": {
       "predeploy": "npm run build",
       "deploy": "gh-pages -d build"
     }
   }
   ```

2. **Install gh-pages:**
   ```bash
   cd frontend
   npm install --save-dev gh-pages
   ```

3. **Create .env.production:**
   ```env
   REACT_APP_API_URL=https://your-backend-url.com
   ```

4. **Deploy:**
   ```bash
   npm run deploy
   ```

5. **Configure GitHub:**
   - Go to repository Settings → Pages
   - Source: gh-pages branch
   - Save

---

## Docker Deployment

### Backend Dockerfile

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ app/

# Create models directory
RUN mkdir -p models

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

Create `frontend/Dockerfile`:

```dockerfile
# Build stage
FROM node:18-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### Docker Compose

Create `docker-compose.yml` in root:

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
    volumes:
      - ./backend/models:/app/models

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
    depends_on:
      - backend
```

### Run with Docker Compose:

```bash
docker-compose up -d
```

---

## Environment Configuration

### Backend (.env)

```env
# Server
API_HOST=0.0.0.0
API_PORT=8000

# CORS
ALLOWED_ORIGINS=https://your-frontend-url.com,http://localhost:3000

# Logging
LOG_LEVEL=INFO

# Optional: Rate limiting
MAX_REQUESTS_PER_MINUTE=60
```

### Frontend (.env.production)

```env
REACT_APP_API_URL=https://your-backend-url.com
```

---

## Post-Deployment

### 1. Test API Endpoints

```bash
# Health check
curl https://your-backend-url.com/health

# Search pitchers
curl "https://your-backend-url.com/api/pitchers/search?query=Cole"
```

### 2. Test Frontend

- Visit your frontend URL
- Search for a pitcher
- Train a model
- Generate predictions

### 3. Monitor Performance

**Backend:**
- Check server logs
- Monitor response times
- Track error rates

**Frontend:**
- Test on multiple devices
- Check loading times
- Verify charts render correctly

### 4. Set up Custom Domain (Optional)

**Vercel:**
```bash
vercel domains add yourdomain.com
```

**Netlify:**
- Domain settings → Add custom domain

**AWS:**
- Route 53 for DNS
- Configure A record pointing to EC2

### 5. Enable HTTPS

**Vercel/Netlify:** Automatic SSL

**AWS/EC2:**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

### 6. Set up Monitoring

**Options:**
- Sentry (error tracking)
- Google Analytics (usage tracking)
- LogRocket (session replay)

---

## Troubleshooting

### CORS Errors

Update backend CORS settings:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-url.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 502 Bad Gateway

- Check backend is running
- Verify port configuration
- Check firewall rules

### Model Not Persisting

- Ensure `models/` directory exists
- Check file permissions
- Consider using cloud storage (S3, GCS)

---

## Scaling Considerations

1. **Database:** Add PostgreSQL for model metadata
2. **Caching:** Use Redis for API responses
3. **CDN:** CloudFlare for static assets
4. **Load Balancer:** Distribute traffic across multiple instances
5. **Background Jobs:** Celery for async model training

---

## Security Best Practices

1. **API Keys:** Store in environment variables
2. **Rate Limiting:** Implement to prevent abuse
3. **Input Validation:** Already implemented in FastAPI
4. **HTTPS:** Always use in production
5. **CORS:** Restrict to specific origins
6. **Updates:** Keep dependencies updated

---

## Cost Estimates

### Free Tier Options:
- **Render:** Free (with limitations)
- **Vercel:** Free for personal projects
- **Netlify:** Free tier available
- **Total:** $0/month

### Paid Options:
- **Railway:** ~$5-10/month
- **AWS EC2:** ~$10-20/month (t2.micro + bandwidth)
- **Custom domain:** ~$12/year
- **Total:** $5-30/month

---

## Maintenance

### Regular Tasks:

1. **Update dependencies:**
   ```bash
   # Backend
   pip install -U -r requirements.txt

   # Frontend
   npm update
   ```

2. **Monitor logs:**
   - Check for errors
   - Review performance metrics

3. **Backup models:**
   - Periodically backup trained models
   - Store in cloud storage

4. **Security patches:**
   - Keep OS and packages updated
   - Review security advisories

---

## Support

For deployment issues:
- Check application logs
- Review platform documentation
- Open GitHub issue

---

**Happy Deploying!**
