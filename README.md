🚀 PresentSir

PresentSir is a smart attendance and academic management platform designed to simplify student attendance tracking, academic administration, and communication workflows.

Built with Django, PresentSir focuses on providing a seamless experience for students, faculty, and administrators while maintaining reliability, security, and scalability.

📖 Project Story

PresentSir started as an idea to solve everyday attendance management challenges faced in educational institutions.

What seemed like a straightforward project quickly evolved into a full-scale web application involving:

Authentication systems
Attendance workflows
Database management
Email services
Production deployment
Security configurations
UI/UX improvements

The project went through multiple iterations, debugging sessions, deployment issues, and feature enhancements before reaching production.

PresentSir represents not just a software project but a journey of continuous learning, problem-solving, and persistence.

✨ Features
👨‍🎓 Student Features
Student Registration
Secure Login
Attendance Tracking
Attendance Reports
Profile Management
Password Reset via Email OTP
👨‍🏫 Faculty Features
Attendance Management
Student Monitoring
Course-wise Attendance Tracking
Report Generation
🏢 Administration Features
Department Management
Course Management
Student Management
Faculty Management
Centralized Dashboard
📧 Email Integration
OTP-based Password Recovery
Secure Email Notifications
Gmail SMTP Integration
🔒 Security Features
Django Authentication
CSRF Protection
Secure Password Storage
Session Management
🛠️ Tech Stack
Backend
Python 3.x
Django
Database
SQLite (Development)
Frontend
HTML
CSS
JavaScript
Django Templates
Deployment
PythonAnywhere
Email Service
Gmail SMTP
🏗️ Project Structure
Present-Sir/
│
├── manage.py
├── db.sqlite3
├── requirements.txt
│
├── presentsir/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── psapp/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   ├── admin.py
│   └── templates/
│
├── staticfiles/
│
└── README.md
⚙️ Installation
Clone Repository
git clone https://github.com/yourusername/PresentSir.git
cd PresentSir
Create Virtual Environment
python -m venv venv
source venv/bin/activate

# Windows
venv\Scripts\activate
Install Dependencies
pip install -r requirements.txt
Run Migrations
python manage.py migrate
Create Superuser
python manage.py createsuperuser
Run Development Server
python manage.py runserver
🔧 Environment Variables

Create environment variables for email services:

export EMAIL_HOST_USER="your-email@gmail.com"
export EMAIL_HOST_PASSWORD="your-app-password"

Django reads:

EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
📬 Email Configuration
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
🚀 Deployment

PresentSir is deployed using:

PythonAnywhere
Django WSGI
Gmail SMTP Services

Deployment involved:

WSGI Configuration
Static Files Collection
Environment Variable Management
Email Service Integration
📈 Future Enhancements
Role-Based Dashboards
Attendance Analytics
Mobile Application
QR-Based Attendance
Face Recognition Attendance
SMS Notifications
Cloud Database Integration
REST API Support
AI-Based Attendance Insights
🎯 Lessons Learned

During the development of PresentSir, I gained practical experience in:

Django Architecture
Authentication Systems
Database Design
Production Deployment
SMTP Email Integration
Error Logging
Debugging Production Issues
Software Engineering Best Practices
🤝 Contributing

Contributions, suggestions, and feedback are welcome.

Fork the repository
Create a feature branch
git checkout -b feature-name
Commit changes
git commit -m "Added feature"
Push branch
git push origin feature-name
Create Pull Request
👨‍💻 Developer

Surya N R

Passionate about building real-world software solutions, exploring technology, and continuously learning through hands-on development.

⭐ Support

If you found this project useful:

⭐ Star the repository
🍴 Fork the repository
💬 Share feedback and suggestions
