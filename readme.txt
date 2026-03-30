Web application for managing Access Points with automatic MAC address detection using image processing (OCR & barcode scanning).

✨ Features
JWT-based authentication
Role-based access control (admin / technician)
AP registration with image upload
Automatic MAC address extraction (OCR + barcode)
Search by room or MAC address
Secure image access
Admin-only deletion of records

How it works:

The system automates AP registration by extracting the MAC address from an uploaded image:
Attempts barcode scanning using pyzbar
Falls back to OCR (Tesseract) if needed
Applies image preprocessing (OpenCV)
Normalizes detected MAC address

Tech Stack
Backend
Python + FastAPI
SQLAlchemy
JWT (python-jose)
Passlib (bcrypt)
SlowAPI (rate limiting)
Image Processing
OpenCV
Pillow
pyzbar
pytesseract
Database
MySQL / MariaDB
Frontend
HTML / CSS / JavaScript
📁 Project Structure
.
├── main.py
├── database.py
├── models.py
├── security.py
├── deps.py
├── routers/
│   ├── auth.py
│   └── aps.py
├── services/
│   └── ocr.py
├── static/
│   └── index.html
├── uploads/
└── requirements.txt

⚙️ Setup
1. Clone the repository
git clone https://github.com/your-username/ap-manager.git
cd ap-manager
2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
3. Install dependencies
pip install -r requirements.txt
🔑 Environment Variables

Create a .env file:

DATABASE_URL=mysql+pymysql://user:password@localhost/db_name
SECRET_KEY=your_secret_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15

▶️ Run the app
uvicorn main:app --reload

📍 Open in browser:
http://127.0.0.1:8000

📡 API Endpoints
Method	Endpoint	Description
POST	/login		User authentication
POST	/aps/		Register AP
GET	/aps/		Search/list APs
GET	/aps/{id}/image	Get AP image
DELETE	/aps/{id}	Delete AP (admin only)
⚠️ Requirements
Python 3.10+
MySQL / MariaDB
Tesseract OCR installed
🔒 Security
Password hashing with bcrypt
JWT authentication
Role-based access control
Rate limiting on login

SQL
Users
-----
id (PK)
username
password
role

APs
-----
id (PK)
room
mac_address
image_path