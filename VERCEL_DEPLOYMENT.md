# Deploying to Vercel - Complete Guide

## Quick Answer

**Yes, you can host on Vercel!** You have two options:

### ✅ Option 1: Frontend Only (Recommended)
- Deploy React frontend to Vercel
- Deploy FastAPI backend to Render/Railway (free)
- **Pros**: Best performance, no limitations
- **Time**: 10 minutes

### ⚠️ Option 2: Full Stack on Vercel
- Deploy both frontend and backend to Vercel
- **Pros**: Everything in one place
- **Cons**: Serverless limitations (timeouts, cold starts, storage)
- **Time**: 15 minutes

---

## Option 1: Frontend on Vercel (Recommended)

This is the **easiest and best** approach.

### Step 1: Deploy Backend to Render

```bash
# 1. Go to render.com and sign up
# 2. Click "New +" → "Web Service"
# 3. Connect GitHub and select your repo
# 4. Configure:

Name: mlb-pitch-predictor-api
Environment: Python 3
Root Directory: backend
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT

# 5. Click "Create Web Service"
# 6. Copy the URL (e.g., https://mlb-pitch-predictor-api.onrender.com)
```

### Step 2: Deploy Frontend to Vercel

```bash
# Install Vercel CLI
npm install -g vercel

# Navigate to your project
cd /path/to/fuzzy-waddle

# Login to Vercel
vercel login

# Deploy frontend
cd frontend
vercel
```

**Follow the prompts:**
```
? Set up and deploy? Yes
? Which scope? [Your account]
? Link to existing project? No
? What's your project's name? mlb-pitch-predictor
? In which directory is your code located? ./
? Want to override settings? No
```

### Step 3: Configure Environment Variable

```bash
# Add your backend URL
vercel env add REACT_APP_API_URL

# When prompted, enter:
https://mlb-pitch-predictor-api.onrender.com

# Select: Production, Preview, Development (all)
```

### Step 4: Deploy to Production

```bash
vercel --prod
```

**Done!** Your app is live at `https://mlb-pitch-predictor.vercel.app`

---

## Option 2: Full Stack on Vercel (Advanced)

Deploy both frontend and backend to Vercel using serverless functions.

### Important Limitations

⚠️ **Serverless Constraints:**
- **10 second timeout** on Hobby plan (model training may timeout)
- **50 second timeout** on Pro plan ($20/month)
- **Cold starts**: First request slower
- **No persistent storage**: Models must be reloaded or stored externally
- **50MB function size limit**

### When to Use This Option

✅ Good for:
- Demo/prototype purposes
- Low traffic applications
- Quick deployments

❌ Not ideal for:
- Production ML apps with heavy computation
- Apps needing persistent model storage

### Setup Instructions

The files have already been created for you:
- `api/index.py` - Vercel serverless entry point
- `api/requirements.txt` - Backend dependencies
- `vercel.json` - Vercel configuration

### Deploy Full Stack

```bash
# From project root
vercel

# Follow prompts:
? Set up and deploy? Yes
? Which scope? [Your account]
? Link to existing project? No
? What's your project's name? mlb-pitch-predictor
? In which directory is your code located? ./
? Want to override settings? No
```

Vercel will:
1. Build React frontend from `frontend/`
2. Deploy Python backend as serverless functions in `api/`
3. Route `/api/*` to backend, everything else to frontend

### Deploy to Production

```bash
vercel --prod
```

### Testing

```bash
# Test API endpoint
curl https://your-app.vercel.app/api/health

# Test frontend
open https://your-app.vercel.app
```

---

## Comparison Table

| Feature | Frontend Only | Full Stack |
|---------|--------------|------------|
| **Setup Time** | 10 min | 15 min |
| **Cost** | Free | Free (Hobby) / $20/mo (Pro) |
| **Performance** | Excellent | Good (cold starts) |
| **Timeouts** | No limits | 10s (Hobby) / 50s (Pro) |
| **Model Storage** | Persistent (Render) | Need external storage |
| **Scalability** | High | Limited |
| **Maintenance** | Two platforms | One platform |
| **Best For** | Production | Demos/Prototypes |

---

## Recommended: Frontend on Vercel + Backend on Render

### Why This is Best

1. **No Limitations**: Render handles ML workloads better
2. **Free**: Both platforms have generous free tiers
3. **Fast**: Vercel optimizes React apps perfectly
4. **Reliable**: Render keeps backend running
5. **Simple**: Each platform does what it's best at

### Complete Setup (10 Minutes)

#### Backend on Render:
1. Go to [render.com](https://render.com)
2. New Web Service → Connect GitHub
3. Select repository
4. Settings:
   ```
   Root Directory: backend
   Build: pip install -r requirements.txt
   Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
5. Create → Copy URL

#### Frontend on Vercel:
```bash
cd frontend
vercel env add REACT_APP_API_URL
# Enter your Render URL
vercel --prod
```

**Done!** 🎉

---

## Troubleshooting

### "Module not found" on Vercel

Update `api/requirements.txt` to ensure all dependencies are listed.

### CORS Errors

The backend's CORS is set to allow all origins (`*`). For production, update `backend/app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-app.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Model Training Timeout (Full Stack)

If using Vercel serverless:
- Reduce `max_games` parameter (try 5-10 instead of 20)
- Upgrade to Pro plan for 50s timeout
- Or use Option 1 (Render backend)

### Cold Starts

Serverless functions "sleep" when idle. First request may take 3-5 seconds.

**Solutions:**
- Use Option 1 (Render stays awake)
- Upgrade to Vercel Pro (less cold starts)
- Implement a ping/keep-alive mechanism

---

## Custom Domain (Optional)

### Add Custom Domain to Vercel

```bash
vercel domains add yourdomain.com
```

Or via dashboard:
1. Project Settings → Domains
2. Add `yourdomain.com`
3. Configure DNS (Vercel provides instructions)
4. SSL is automatic

---

## Environment Variables

### Frontend (.env.production)

```env
REACT_APP_API_URL=https://your-backend-url.com
```

### Set in Vercel:

**Via CLI:**
```bash
vercel env add REACT_APP_API_URL
```

**Via Dashboard:**
1. Project Settings → Environment Variables
2. Add `REACT_APP_API_URL`
3. Set value to your backend URL
4. Apply to: Production, Preview, Development

---

## Monitoring

### Vercel Dashboard

- View deployment logs
- Monitor function execution
- Track errors and performance

### Render Dashboard (if using)

- View backend logs
- Monitor uptime
- Check resource usage

---

## Cost Breakdown

### Free Tier (Recommended Setup)

| Service | Plan | Cost |
|---------|------|------|
| Vercel (Frontend) | Hobby | $0 |
| Render (Backend) | Free | $0 |
| **Total** | | **$0/month** |

**Limits:**
- Vercel: 100GB bandwidth, 100 deployments/day
- Render: 750 hours/month, sleeps after 15min inactivity

### Paid Tier (If Needed)

| Service | Plan | Cost |
|---------|------|------|
| Vercel (Full Stack) | Pro | $20/month |
| Render (Backend) | Starter | $7/month |

**Benefits:**
- No sleep on Render
- 50s timeouts on Vercel
- Better performance
- Commercial use allowed

---

## Final Recommendation

### For Development/Learning:
✅ **Option 1** - Frontend on Vercel (free) + Backend on Render (free)

### For Production:
✅ **Option 1** - Frontend on Vercel (free/Pro) + Backend on Render (Starter $7/mo)

### For Quick Demo:
✅ **Option 2** - Full stack on Vercel (free/Pro)

---

## Step-by-Step: Easiest Path

1. **Deploy backend to Render** (5 min)
   - render.com → New Web Service → Connect repo
   - Root: `backend`, Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Copy the URL

2. **Deploy frontend to Vercel** (5 min)
   ```bash
   cd frontend
   vercel env add REACT_APP_API_URL  # paste Render URL
   vercel --prod
   ```

3. **Test the app** (2 min)
   - Open your Vercel URL
   - Search for "Cole"
   - Train model
   - Make predictions

**Total Time: 12 minutes** ⚡

---

## Need Help?

- Vercel Docs: https://vercel.com/docs
- Render Docs: https://render.com/docs
- This repo's issues: [GitHub Issues]

---

**Happy deploying!** 🚀
