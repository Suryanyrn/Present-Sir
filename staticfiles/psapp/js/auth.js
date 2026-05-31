// --- 1. GLOBAL HELPERS ---

function getCSRFToken() {
    const el = document.getElementById('csrf-token');
    return el ? el.value.trim() : '';
}

function setLoading(buttonId, isLoading, loadingText = "Processing...") {
    const btn = document.getElementById(buttonId);
    if (!btn) return;

    if (isLoading) {
        if (!btn.dataset.originalText) btn.dataset.originalText = btn.innerText;
        btn.disabled = true;
        btn.classList.add('opacity-75', 'cursor-not-allowed');
        btn.innerHTML = `
            <div class="flex items-center justify-center">
                <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                ${loadingText}
            </div>`;
    } else {
        btn.disabled = false;
        btn.classList.remove('opacity-75', 'cursor-not-allowed');
        btn.innerText = btn.dataset.originalText || "Submit";
    }
}

function setStatus(message, isError = false) {
    const statusMessage = document.getElementById('status-message');
    if (!statusMessage) return;

    statusMessage.textContent = message;
    statusMessage.className = `p-3 rounded-lg text-sm text-center transition-opacity duration-300 opacity-100 ${isError ? 'bg-red-900/50 text-red-200 border border-red-800' : 'bg-green-900/50 text-green-200 border border-green-800'}`;
    statusMessage.classList.remove('hidden');

    // Hide after 5 seconds
    setTimeout(() => {
        statusMessage.classList.remove('opacity-100');
        setTimeout(() => statusMessage.classList.add('hidden'), 300);
    }, 5000);
}

// --- 2. FORM ANIMATION & TOGGLE ---

function animateTitle(titleId, text) {
    const titleElement = document.getElementById(titleId);
    if (!titleElement) return;
    titleElement.innerHTML = '';
    text.split('').forEach((char, index) => {
        const span = document.createElement('span');
        span.textContent = char;
        span.classList.add('app-title-letter');
        if (char === ' ') span.classList.add('space-char');
        span.style.animationDelay = `${index * 0.03}s`;
        titleElement.appendChild(span);
    });
}

function showForm(formName) {
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const forgotForm = document.getElementById('forgot-form');
    const loginTab = document.getElementById('login-tab');
    const registerTab = document.getElementById('register-tab');

    // Hide all forms
    [loginForm, registerForm, forgotForm].forEach(form => {
        if (form) {
            form.classList.add('fade-out');
            form.classList.remove('fade-in');
            setTimeout(() => form.style.display = 'none', 400);
        }
    });

    // Reset Tabs
    if (loginTab) loginTab.className = "flex-1 py-3 text-sm font-semibold rounded-lg transition duration-300 text-slate-300 hover:text-white hover:bg-slate-700";
    if (registerTab) registerTab.className = "flex-1 py-3 text-sm font-semibold rounded-lg transition duration-300 text-slate-300 hover:text-white hover:bg-slate-700";

    // Activate specific form
    let activeForm;
    if (formName === 'login') {
        activeForm = loginForm;
        if (loginTab) loginTab.className = "flex-1 py-3 text-sm font-semibold rounded-lg transition duration-300 text-white bg-blue-600 shadow-md";
    } else if (formName === 'register') {
        activeForm = registerForm;
        if (registerTab) registerTab.className = "flex-1 py-3 text-sm font-semibold rounded-lg transition duration-300 text-white bg-teal-500 shadow-md";
    } else {
        activeForm = forgotForm;
    }

    if (activeForm) {
        setTimeout(() => {
            activeForm.style.display = 'block';
            void activeForm.offsetWidth; // Force reflow
            activeForm.classList.remove('fade-out');
            activeForm.classList.add('fade-in');
        }, 400);
    }
}

// --- 3. INPUT VALIDATION ---

function updateFeedback(id, isValid, message) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = isValid ? `✓ ${message}` : `❌ ${message}`;
        element.classList.toggle('text-green-400', isValid);
        element.classList.toggle('text-red-400', !isValid);
    }
}

function checkNameValidity() {
    const name = document.getElementById('register-name').value.trim();
    const feedback = document.getElementById('name-feedback');
    const nameRegex = /^[a-zA-Z\s.]+$/;

    if (name.length === 0) {
        feedback.textContent = '';
        return false;
    }
    if (!nameRegex.test(name)) {
        feedback.textContent = '❌ Name should only contain letters, spaces, and periods.';
        feedback.classList.replace('text-green-400', 'text-red-400');
        return false;
    }
    feedback.textContent = '✓ Valid Name format.';
    feedback.classList.replace('text-red-400', 'text-green-400');
    return true;
}

function checkPasswordValidity() {
    const password = document.getElementById('register-password').value;
    const confirmPassword = document.getElementById('register-confirm-password').value;

    const lengthValid = password.length >= 8;
    const letterValid = /[a-zA-Z]/.test(password);
    const digitValid = /\d/.test(password);
    const specialValid = /[\W_]/.test(password);
    const matchValid = password === confirmPassword && password.length > 0;

    updateFeedback('feedback-length', lengthValid, 'Min 8 characters');
    updateFeedback('feedback-letter', letterValid, 'Contains letters');
    updateFeedback('feedback-digit', digitValid, 'Contains a number');
    updateFeedback('feedback-special', specialValid, 'Contains special char');

    const matchEl = document.getElementById('feedback-match');
    if (password.length > 0) {
        matchEl.classList.remove('hidden');
        updateFeedback('feedback-match', matchValid, matchValid ? 'Passwords match' : 'Passwords do not match');
    } else {
        matchEl.classList.add('hidden');
    }

    // Enable/Disable Register Button (Depends on OTP verified state too)
    const btn = document.getElementById('register-btn');
    const isComplex = lengthValid && letterValid && digitValid && specialValid && matchValid;

    // We check a global variable for OTP verification
    if (window.isEmailVerified && isComplex) {
        btn.disabled = false;
        btn.classList.remove('opacity-50');
    } else {
        btn.disabled = true;
        btn.classList.add('opacity-50');
    }

    return isComplex;
}

// --- 4. AUTHENTICATION HANDLERS ---

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById("login-email").value;
    const password = document.getElementById("login-password").value;
    const csrf = getCSRFToken();

    setLoading('login-btn', true, "Signing In...");

    try {
        const res = await fetch("/login/", {
            method: "POST",
            // CRITICAL: Send cookies for session handling
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRFToken": csrf
            },
            body: new URLSearchParams({ email, password })
        });

        const out = await res.text();

        if (out === "LOGIN_SUCCESS") {
            window.location.href = "/dashboard/";
        } else if (out === "NOT_VERIFIED") {
            setStatus("Please verify your email before login.", true);
            setLoading('login-btn', false);
        } else {
            setStatus("Invalid email or password.", true);
            setLoading('login-btn', false);
        }
    } catch (err) {
        setStatus("Network Error", true);
        setLoading('login-btn', false);
    }
}

// Registration State
window.isEmailVerified = false;

async function handleRegister(e) {
    e.preventDefault();

    // Safety check
    if (!window.isEmailVerified) return alert("Verify Email First!");

    setLoading('register-btn', true, "Creating Account...");

    const form = document.getElementById('register-form');
    const data = new FormData(form);

    try {
        const res = await fetch('/register/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { "X-CSRFToken": getCSRFToken() },
            body: data
        });

        const result = await res.text();

        if (result === "REGISTERED") {
            alert("Account created successfully!");
            form.reset();
            document.getElementById("otp-status").classList.add("hidden");
            document.getElementById("register-email").readOnly = false;
            window.isEmailVerified = false;
            setLoading('register-btn', false);
            showForm("login");
        } else {
            setStatus("Registration failed. Try again.", true);
            setLoading('register-btn', false);
        }
    } catch (err) {
        setStatus("Network error", true);
        setLoading('register-btn', false);
    }
}

// --- 5. OTP LOGIC ---

let countdown = 60;
let timerInterval = null;

async function sendOTP() {
    const email = document.getElementById('register-email').value;
    const csrf = getCSRFToken();

    if (!email) return alert("Enter email first!");

    setLoading('send-otp-btn', true, "Sending...");

    try {
        const res = await fetch('/send-otp/', {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRFToken": csrf
            },
            body: new URLSearchParams({ email })
        });

        const result = await res.text();

        if (result === "EMAIL_EXISTS") {
            alert("Email already exists! Please login.");
            setLoading('send-otp-btn', false);
            return;
        }
        if (result === "OTP_SENT") {
            alert("OTP sent to your email!");
            setLoading('send-otp-btn', false);

            document.getElementById("register-email").readOnly = true;
            document.getElementById("otp-section").classList.remove("hidden");
            document.getElementById("masked-email").innerText = "Check your inbox.";
            document.getElementById("masked-email").classList.remove("hidden");

            // Start Timer
            const btn = document.getElementById("send-otp-btn");
            btn.disabled = true;
            countdown = 30;
            timerInterval = setInterval(() => {
                countdown--;
                btn.innerText = `Retry in ${countdown}s`;
                if (countdown <= 0) {
                    clearInterval(timerInterval);
                    btn.disabled = false;
                    btn.innerText = "Send OTP";
                }
            }, 1000);
        } else {
            setLoading('send-otp-btn', false);
            alert("Could not send OTP.");
        }
    } catch (err) {
        setLoading('send-otp-btn', false);
        alert("Network Error");
    }
}

// Renamed locally to match the function definition
async function handleOTPVerify() {
    const email = document.getElementById("register-email").value;
    const otp = document.getElementById("otp-input").value;
    const csrf = getCSRFToken();

    const res = await fetch('/verify-email-otp/', {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": csrf
        },
        body: new URLSearchParams({ email, otp })
    });

    const result = await res.text();
    const status = document.getElementById("otp-status");
    const successBox = document.getElementById("otp-success");

    if (result === "VERIFIED") {
        window.isEmailVerified = true;
        status.innerHTML = `<span class='text-green-400 font-bold'>OTP Verified</span>`;
        status.classList.remove("hidden");

        successBox.innerHTML = `<div class="checkmark"></div>`;
        successBox.classList.remove("hidden");

        document.getElementById("otp-section").classList.add("hidden");

        // Re-check password validity to enable button
        checkPasswordValidity();

    } else {
        status.innerHTML = `<span class='text-red-400 font-bold'>Incorrect OTP!</span>`;
        status.classList.remove("hidden");
    }
}

// --- 6. FORGOT PASSWORD ---

async function fpSendOTP() {
    const email = document.getElementById("forgot-email").value;
    const csrf = getCSRFToken();
    setLoading('forgot-btn', true, "Sending...");

    const res = await fetch("/forgot-send-otp/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": csrf
        },
        body: new URLSearchParams({ email })
    });

    const out = await res.text();

    if (out === "NO_EMAIL") {
        alert("Email not registered!");
        setLoading('forgot-btn', false);
        return;
    }

    if (out === "FP_OTP_SENT") {
        alert("OTP sent!");
        document.getElementById("fp-otp-section").classList.remove("hidden");
        setLoading('forgot-btn', false);
    }
}

async function fpVerifyOTP() {
    const email = document.getElementById("forgot-email").value;
    const otp = document.getElementById("fp-otp").value;
    const csrf = getCSRFToken();

    const res = await fetch("/forgot-verify-otp/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": csrf
        },
        body: new URLSearchParams({ email, otp })
    });

    const out = await res.text();
    const status = document.getElementById("fp-status");

    if (out === "FP_VERIFIED") {
        status.innerHTML = "✔ Verified";
        status.classList.remove("hidden");
        status.classList.add("text-green-400");
        document.getElementById("fp-newpass-section").classList.remove("hidden");
    } else {
        status.innerHTML = "✘ Incorrect";
        status.classList.remove("hidden");
        status.classList.add("text-red-400");
    }
}

function checkResetPasswordValidity() {
    const password = document.getElementById('fp-password').value;
    const confirmPassword = document.getElementById('fp-confirm-password').value;
    const matchValid = password === confirmPassword && password.length >= 8;
    return matchValid;
}

async function fpResetPassword() {
    if (!checkResetPasswordValidity()) {
        alert("Passwords must match and be at least 8 chars.");
        return;
    }
    const newpass = document.getElementById("fp-password").value;
    const csrf = getCSRFToken();

    const res = await fetch("/reset-password/", {
        method: "POST",
        credentials: "same-origin",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": csrf
        },
        body: new URLSearchParams({ password: newpass })
    });

    const out = await res.text();

    if (out === "PASSWORD_RESET") {
        alert("Password reset successful! Please login.");
        showForm("login");
    }
}

// --- INITIALIZATION & BINDING ---

window.onload = function () {
    animateTitle('app-title', 'Present Sir!!!');
    // Set initial state
    const reg = document.getElementById('register-form');
    const forgot = document.getElementById('forgot-form');
    if (reg) reg.style.display = 'none';
    if (forgot) forgot.style.display = 'none';
};

// EXPORT FUNCTIONS TO WINDOW SO HTML ONCLICK CAN SEE THEM
// This is where your error was (verifyOTP vs handleOTPVerify)
window.handleOTPVerify = handleOTPVerify; // <--- FIXED THIS LINE
window.showForm = showForm;
window.handleLogin = handleLogin;
window.handleRegister = handleRegister;
window.checkPasswordValidity = checkPasswordValidity;
window.checkNameValidity = checkNameValidity;
window.sendOTP = sendOTP;
window.fpSendOTP = fpSendOTP;
window.fpVerifyOTP = fpVerifyOTP;
window.fpResetPassword = fpResetPassword;
window.checkResetPasswordValidity = checkResetPasswordValidity;