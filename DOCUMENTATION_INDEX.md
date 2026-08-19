# 📚 ROV-GUI Dokumentasi Index

Panduan navigasi lengkap untuk semua dokumentasi ROV-GUI system.

## 📖 File Dokumentasi

### 1. **README.md** (19.88 KB) ⭐ Mulai di sini
Dokumentasi utama project yang mencakup:
- Pengenalan dan overview project
- Struktur project
- Tech stack yang digunakan
- Panduan instalasi lengkap (backend & frontend)
- **Dokumentasi API Endpoints yang komprehensif**
- Arsitektur dan data flow
- Features project
- Troubleshooting umum
- Development guide

**Untuk siapa**: Developer baru, tech lead, stakeholder  
**Dibaca ketika**: Pertama kali setup project

---

### 2. **API_DOCUMENTATION.md** (17.52 KB) ⭐ Untuk Developer API
Referensi lengkap untuk semua API endpoints:
- Overview API
- Base URL dan konfigurasi
- Authentication (saat ini: none)
- Format request/response
- **Endpoint: GET /api/telemetry** dengan contoh lengkap
- **Endpoint: POST /api/source** dengan contoh lengkap
- Response status codes
- Error handling
- Rate limiting
- Contoh penggunaan advanced (monitoring loop, batch collection)
- Polishing strategy
- Error response patterns

**Untuk siapa**: API consumer, frontend developer, integration engineer  
**Dibaca ketika**: Mengintegrasikan API ke aplikasi lain

---

### 3. **SETUP_GUIDE.md** (12.90 KB) 🛠️ Untuk Setup & Deployment
Panduan detail untuk setup development dan production:
- Prerequisites (hardware & software)
- Quick Start (5 menit untuk bisa jalan)
- Detailed setup langkah-demi-langkah
- Konfigurasi BlueOS untuk MAVLink
- Testing strategy (manual & automated)
- Production deployment dengan gunicorn + nginx
- Docker deployment
- Troubleshooting umum
- Testing script Python

**Untuk siapa**: DevOps, deployment engineer, system admin  
**Dibaca ketika**: Melakukan setup awal atau deployment ke production

---

### 4. **API_QUICK_REFERENCE.md** (5.08 KB) ⚡ Quick Lookup
Referensi cepat untuk developer yang sudah familiar:
- Base URL
- Table overview endpoints
- Contoh cepat untuk setiap endpoint
- Field descriptions
- Code examples (JavaScript, Python, cURL)
- Common use cases
- Status codes
- Troubleshooting singkat

**Untuk siapa**: Developer yang sudah familiar dengan project  
**Dibaca ketika**: Perlu reminder cepat tentang endpoint

---

## 🚀 Panduan Cepat Berdasarkan Role

### Saya seorang **Frontend Developer**

1. Baca bagian Installation di **README.md**
2. Ikuti **SETUP_GUIDE.md** untuk setup dev environment
3. Refer ke **API_QUICK_REFERENCE.md** saat mengintegrasikan API
4. Konsultasikan **API_DOCUMENTATION.md** untuk detail endpoint

**Contoh workflow:**
```bash
# Setup
cd rov-gui/frontend && npm install && npm run dev

# API calls di code
fetch('http://localhost:5001/api/telemetry')
```

---

### Saya seorang **Backend Developer / API Engineer**

1. Baca **README.md** untuk overview project
2. Pelajari **API_DOCUMENTATION.md** secara mendetail
3. Gunakan **SETUP_GUIDE.md** untuk testing API
4. Refer ke **API_QUICK_REFERENCE.md** untuk cheat sheet

**Contoh workflow:**
```bash
# Setup & testing
cd rov-gui/backend && python -m venv venv && source venv/bin/activate
pip install flask flask-cors pymavlink
python rov-depth.py

# Test dengan curl atau Python
curl http://localhost:5001/api/telemetry
```

---

### Saya ingin **Deploy ke Production**

1. Baca deployment section di **README.md**
2. Ikuti **SETUP_GUIDE.md** bagian "Production Deployment"
3. Gunakan **API_DOCUMENTATION.md** untuk implement authentication
4. Test dengan script di **SETUP_GUIDE.md**

**Contoh workflow:**
```bash
# Production dengan gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 rov-depth:app
```

---

### Saya ingin **Integrasikan ROV-GUI ke Aplikasi Lain**

1. Baca overview di **API_QUICK_REFERENCE.md**
2. Konsultasikan **API_DOCUMENTATION.md** untuk detail
3. Lihat contoh di bagian "Examples" untuk implementation
4. Refer ke status codes & error handling

**Contoh workflow:**
```javascript
// Integrasi ke aplikasi lain
const rovApi = {
  getTelemetry: () => fetch('http://rov-server/api/telemetry').then(r => r.json()),
  switchSource: (src) => fetch('http://rov-server/api/source', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: src })
  })
};
```

---

## 📋 Checklist Sebelum Deploy

- [ ] Setup backend di **SETUP_GUIDE.md**
- [ ] Konfigurasi BlueOS MAVLink (lihat **SETUP_GUIDE.md**)
- [ ] Setup frontend
- [ ] Test API endpoints dengan script di **SETUP_GUIDE.md**
- [ ] Verify telemetry data real-time
- [ ] Test switch data source
- [ ] Run production build
- [ ] Setup gunicorn + nginx (lihat **SETUP_GUIDE.md**)
- [ ] Configure firewall (port 5001, 14552, dll)
- [ ] Setup monitoring dan logging
- [ ] Consider security (authentication, rate limiting, etc)

---

## 🔗 Navigasi Cross-Reference

### API Endpoints Details

| Endpoint | Quick Ref | Full Doc | Setup Notes |
|----------|-----------|----------|-------------|
| GET /api/telemetry | [Link](API_QUICK_REFERENCE.md#1-get-apitelemetry) | [Link](API_DOCUMENTATION.md#endpoint-get-apitelemetry) | Real-time polling |
| POST /api/source | [Link](API_QUICK_REFERENCE.md#2-post-apisource) | [Link](API_DOCUMENTATION.md#endpoint-post-apisource) | Source switching |

### Setup Guides

| Bagian | File | Link |
|--------|------|------|
| Install Python | SETUP_GUIDE.md | [Link](SETUP_GUIDE.md#step-1-install-python) |
| Install Node.js | SETUP_GUIDE.md | [Link](SETUP_GUIDE.md#step-1-install-nodejs) |
| Configure BlueOS | SETUP_GUIDE.md | [Link](SETUP_GUIDE.md#konfigurasi-blueos) |
| Test API | SETUP_GUIDE.md | [Link](SETUP_GUIDE.md#1-test-backend-api) |
| Production Deploy | SETUP_GUIDE.md | [Link](SETUP_GUIDE.md#production-deployment) |

---

## 🎯 Task-Based Documentation Map

### "Saya ingin menjalankan project di local"
→ **SETUP_GUIDE.md** → Quick Start section

### "Saya ingin tahu API apa yang tersedia"
→ **API_QUICK_REFERENCE.md** (5 menit) atau **API_DOCUMENTATION.md** (detail)

### "Saya perlu integrate ROV-GUI ke mobile app"
→ **API_DOCUMENTATION.md** + **API_QUICK_REFERENCE.md**

### "Saya ingin setup production server"
→ **SETUP_GUIDE.md** → Production Deployment section

### "Saya ingin understand architecture"
→ **README.md** → Architecture section

### "Saya ingin troubleshoot connection issues"
→ **README.md** atau **SETUP_GUIDE.md** → Troubleshooting section

### "Saya ingin implement authentication"
→ **API_DOCUMENTATION.md** → Authentication section + custom implementation

---

## 📊 Dokumentasi Overview

```
ROV-GUI Documentation
│
├── README.md ⭐
│   ├── Overview & Features
│   ├── Installation Guide
│   ├── API Endpoints Summary
│   ├── Architecture
│   ├── Troubleshooting
│   └── Development
│
├── API_DOCUMENTATION.md ⭐
│   ├── API Overview
│   ├── Base URL & Authentication
│   ├── GET /api/telemetry (detailed)
│   ├── POST /api/source (detailed)
│   ├── Error Handling
│   ├── Examples & Patterns
│   └── Changelog
│
├── API_QUICK_REFERENCE.md ⚡
│   ├── Quick Lookup
│   ├── Code Snippets
│   ├── Common Use Cases
│   └── Troubleshooting
│
└── SETUP_GUIDE.md 🛠️
    ├── Prerequisites
    ├── Quick Start
    ├── Detailed Setup
    ├── BlueOS Configuration
    ├── Testing Strategy
    ├── Production Deployment
    └── Troubleshooting
```

---

## 💡 Tips Penggunaan Dokumentasi

1. **Pertama kali?** → Baca README.md utuh, kemudian SETUP_GUIDE.md Quick Start

2. **Ingin paham API?** → Mulai API_QUICK_REFERENCE.md, lalu deep dive ke API_DOCUMENTATION.md

3. **Setup production?** → Langsung ke SETUP_GUIDE.md bagian Production Deployment

4. **Integrasikan ke project lain?** → API_DOCUMENTATION.md examples + API_QUICK_REFERENCE.md

5. **Ada error?** → Troubleshooting section di README.md atau SETUP_GUIDE.md

---

## 📞 Support & Resources

- **Backend Issues**: Check SETUP_GUIDE.md Troubleshooting
- **API Integration**: See API_DOCUMENTATION.md Examples
- **Deployment**: See SETUP_GUIDE.md Production Deployment
- **Architecture Questions**: See README.md Architecture section

---

## 📝 Informasi File

| File | Size | Lines | Updated |
|------|------|-------|---------|
| README.md | 19.88 KB | ~600 | 2026-08-19 |
| API_DOCUMENTATION.md | 17.52 KB | ~550 | 2026-08-19 |
| SETUP_GUIDE.md | 12.90 KB | ~400 | 2026-08-19 |
| API_QUICK_REFERENCE.md | 5.08 KB | ~150 | 2026-08-19 |

**Total Documentation**: ~55 KB, comprehensive coverage of all aspects

---

**Happy coding! 🚀**

Untuk pertanyaan atau klarifikasi, refer ke file dokumentasi yang sesuai atau hubungi tim development.
