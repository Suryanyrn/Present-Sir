# 🚀 PresentSir

**PresentSir** is a smart attendance and academic management platform designed to simplify student attendance tracking, academic administration, and communication workflows.

Built with **Django**, PresentSir focuses on providing a seamless experience for students, faculty, and administrators while maintaining reliability, security, and scalability.

---

# 📖 Project Story

PresentSir started as an idea to solve everyday attendance management challenges faced in educational institutions.

What seemed like a straightforward project quickly evolved into a full-scale web application involving authentication systems, attendance workflows, database management, email services, production deployment, security configurations, and user experience improvements.

The project went through multiple iterations, debugging sessions, deployment issues, and feature enhancements before reaching production.

PresentSir represents not just a software project but a journey of continuous learning, problem-solving, and persistence.

---

# ✨ Features

## 👨‍🎓 Student Features

* Student Registration
* Secure Login
* Attendance Tracking
* Attendance Reports
* Profile Management
* Password Reset via Email OTP

## 👨‍🏫 Faculty Features

* Attendance Management
* Student Monitoring
* Course-wise Attendance Tracking
* Report Generation

## 🏢 Administration Features

* Department Management
* Course Management
* Student Management
* Faculty Management
* Centralized Dashboard

## 📧 Email Integration

* OTP-Based Password Recovery
* Secure Email Notifications
* Gmail SMTP Integration

## 🔒 Security Features

* Django Authentication System
* CSRF Protection
* Secure Password Storage
* Session Management

---

# 🛠️ Tech Stack

### Backend

* Python
* Django

### Database

* SQLite

### Frontend

* HTML
* CSS
* JavaScript
* Django Templates

### Deployment

* PythonAnywhere

### Email Service

* Gmail SMTP

---

# 📂 Project Structure

Present-Sir/

├── manage.py

├── db.sqlite3

├── requirements.txt

├── presentsir/

│ ├── settings.py

│ ├── urls.py

│ ├── wsgi.py

│ └── asgi.py

├── psapp/

│ ├── models.py

│ ├── views.py

│ ├── urls.py

│ ├── forms.py

│ ├── admin.py

│ └── templates/

├── staticfiles/

└── README.md

---

# ⚙️ Installation

### Clone Repository

git clone https://github.com/yourusername/PresentSir.git

cd PresentSir

### Create Virtual Environment

python -m venv venv

source venv/bin/activate

Windows:

venv\Scripts\activate

### Install Dependencies

pip install -r requirements.txt

### Run Migrations

python manage.py migrate

### Create Superuser

python manage.py createsuperuser

### Run Development Server

python manage.py runserver

---

# 🔧 Environment Variables

Set the following environment variables:

EMAIL_HOST_USER=[your-email@gmail.com](mailto:your-email@gmail.com)

EMAIL_HOST_PASSWORD=your-app-password

Example in Django:

EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")

EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")

---

# 📬 Email Configuration

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = "smtp.gmail.com"

EMAIL_PORT = 587

EMAIL_USE_TLS = True

---

# 🚀 Deployment

PresentSir is deployed using:

* PythonAnywhere
* Django WSGI Configuration
* Gmail SMTP Services

Deployment involved:

* WSGI Configuration
* Static Files Collection
* Environment Variable Management
* SMTP Email Integration
* Production Debugging

---

# 📈 Future Enhancements

* QR-Based Attendance
* Face Recognition Attendance
* Mobile Application
* Attendance Analytics Dashboard
* SMS Notifications
* REST APIs
* Cloud Database Integration
* AI-Based Attendance Insights

---

# 🎯 What I Learned

Developing PresentSir helped me gain hands-on experience in:

* Django Project Architecture
* Authentication & Authorization
* Database Design
* SMTP Email Services
* Deployment on PythonAnywhere
* Error Logging & Debugging
* Production Environment Management
* Software Engineering Best Practices

---

# 🤝 Contributing

Contributions are welcome.

1. Fork the repository
2. Create a feature branch

git checkout -b feature-name

3. Commit your changes

git commit -m "Added new feature"

4. Push the branch

git push origin feature-name

5. Open a Pull Request

---

# 👨‍💻 Developer

**Surya N R**

Aspiring Software Engineer passionate about building impactful products, solving real-world problems, and continuously learning through development.

---

# ⭐ Support

If you found this project useful:

⭐ Star the repository

🍴 Fork the repository

💬 Share feedback and suggestions

---

> "Every successful deployment hides hundreds of errors that were solved along the way."
