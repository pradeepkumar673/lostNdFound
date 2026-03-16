# CampusLostFound — Frontend

> The most beautiful campus lost & found app ever built. AI-powered, real-time, premium.

---

## 🚀 Tech Stack

| Layer | Tech |
|-------|------|
| Framework | React 18 + TypeScript + Vite |
| Styling | Tailwind CSS 3 + custom design system |
| State | Zustand (persist) + TanStack Query v5 |
| Routing | React Router v6 |
| Animations | Framer Motion 11 |
| Real-time | Socket.IO Client v4 |
| Forms | Zod validation |
| Maps | Leaflet + react-leaflet |
| Uploads | react-dropzone |
| Toasts | Sonner |
| Icons | Lucide React |
| PWA | vite-plugin-pwa |

---

## 📂 Project Structure

```
src/
├── app/                   # globals.css
├── components/
│   ├── common/            # AppLayout, AuthLayout, NotificationBell
│   ├── ui/                # Skeleton
│   ├── item/              # ItemCard, ImageSearchModal
│   └── chat/              # ChatPanel
├── lib/
│   ├── api.ts             # Axios instance + all API calls
│   ├── socket.ts          # Socket.IO client
│   ├── queryClient.ts     # TanStack Query config
│   └── utils.ts           # cn, formatRelativeTime, etc.
├── pages/
│   ├── LandingPage.tsx
│   ├── LoginPage.tsx
│   ├── RegisterPage.tsx
│   ├── DashboardPage.tsx
│   ├── ItemsPage.tsx
│   ├── NewItemPage.tsx    # 4-step AI wizard
│   ├── ItemDetailPage.tsx # Full detail + chat panel + matches
│   ├── MatchesPage.tsx
│   ├── ChatPage.tsx
│   ├── NotificationsPage.tsx
│   ├── HeatmapPage.tsx
│   └── ProfilePage.tsx
├── store/
│   └── index.ts           # Zustand store (auth + ui + notifications)
├── types/
│   └── index.ts           # All TypeScript types
└── App.tsx                # Route definitions
```

---

## ⚙️ Setup

### 1. Install dependencies

```bash
npm install
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```
VITE_API_BASE_URL=http://localhost:5000/api
VITE_SOCKET_URL=http://localhost:5000
```

### 3. Run dev server

```bash
npm run dev
```

Frontend runs at `http://localhost:5173`.

---

## 🔗 Backend Requirements

This frontend connects to the Flask + SocketIO + Gemini + CLIP backend. The backend should expose:

### REST API endpoints (under `/api`):
- `POST /auth/login` / `/auth/register` / `GET /auth/me` / `PATCH /auth/profile`
- `GET /items` (with filters) / `POST /items` / `GET /items/:id` / `PATCH /items/:id` / `DELETE /items/:id`
- `POST /items/analyze` (Gemini + CLIP analysis)
- `POST /items/search-by-image` (CLIP visual search)
- `GET /items/:id/matches` / `POST /items/:id/claim` / `PATCH /items/:id/resolve`
- `GET /matches` / `PATCH /matches/:id/confirm` / `PATCH /matches/:id/reject`
- `GET /chat/rooms` / `POST /chat/rooms` / `GET /chat/rooms/:id/messages` / `POST /chat/rooms/:id/messages`
- `GET /notifications` / `PATCH /notifications/:id/read` / `PATCH /notifications/read-all`
- `GET /stats` / `GET /stats/heatmap`

### Socket.IO events (emitted by server):
- `notification:new` → new notification object
- `match:found` → new match found
- `item:updated` → item status changed
- `message:new` → new chat message in room
- `user:typing` / `user:stop-typing` → typing indicators

---

## 🎨 Design System

### Colors
- **Emerald** (#10b981) — primary CTA, accents, active states
- **Navy/Slate** — dark backgrounds and glass surfaces
- **Indigo** — secondary accents

### Components
- `.glass` — glassmorphism card (backdrop-blur + dark border)
- `.btn-emerald` — primary CTA button with glow
- `.badge-lost` / `.badge-found` — item type badges
- `.match-badge` — AI match % badge with emerald glow
- `.input-base` — consistent form input styling
- `.bubble-sent` / `.bubble-received` — chat bubbles
- `.skeleton` — shimmer loading skeleton

### Fonts
- **DM Sans** — body text
- **Clash Display** (or DM Sans bold) — headings
- **JetBrains Mono** — code/mono

---

## 🏗 Build for Production

```bash
npm run build
```

Output in `dist/`. Deploy to Vercel, Netlify, or any static host.

---

## 📱 PWA

The app is PWA-ready with `vite-plugin-pwa`. Install from the browser on mobile for a native-like experience.

---

## ✨ Key Features

- **AI-Powered Posting Wizard**: 4-step form with Gemini + CLIP auto-fill
- **Visual Search**: Upload a photo to find similar items using CLIP
- **Real-time Everything**: Socket.IO for messages, matches, notifications
- **AI Match Cards**: Similarity % badges with match reasons
- **Campus Heatmap**: Leaflet map showing lost/found density
- **Full Chat**: Real-time messaging with typing indicators + read receipts
- **Badges & Points**: Gamification for finding and returning items
- **Dark/Light Mode**: Premium dark-first design with elegant light mode

Built with ❤️ for campuses everywhere.
