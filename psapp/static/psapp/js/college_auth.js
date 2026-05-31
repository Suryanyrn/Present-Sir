// ==========================================
//  COLLEGE AUTHENTICATION LOGIC (SAFE MODE)
// ==========================================

// 1. GLOBAL HELPERS (Defined directly on window)
window.getCSRFToken = function() {
    const el = document.getElementById('csrf-token');
    return el ? el.value.trim() : '';
};

window.setLoading = function(btnId, isLoading, text = "Processing...") {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    
    if (isLoading) {
        if (!btn.dataset.ogText) btn.dataset.ogText = btn.innerText;
        btn.disabled = true;
        btn.innerHTML = `<svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white inline" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> ${text}`;
        btn.classList.add('opacity-75', 'cursor-not-allowed');
    } else {
        btn.disabled = false;
        btn.innerText = btn.dataset.ogText || "Submit";
        btn.classList.remove('opacity-75', 'cursor-not-allowed');
    }
};

window.setStatus = function(msg, isError = false) {
    const el = document.getElementById('status-message');
    if (!el) return;
    
    el.innerHTML = isError ? `⚠️ ${msg}` : `✅ ${msg}`;
    // Reset classes first
    el.className = `p-3 rounded-lg text-sm text-center font-medium transition-all duration-300 transform scale-100 ${isError ? 'bg-red-900/80 text-red-200 border border-red-700' : 'bg-green-900/80 text-green-200 border border-green-700'}`;
    
    el.classList.remove('hidden', 'opacity-0');
    
    // Auto hide
    setTimeout(() => { 
        el.classList.add('opacity-0'); 
        setTimeout(() => el.classList.add('hidden'), 300); 
    }, 4000);
};

// 2. TOGGLE FORMS
window.showForm = function(type) {
    const loginForm = document.getElementById('login-form');
    const regForm = document.getElementById('register-form');
    const forgotForm = document.getElementById('forgot-form');
    const loginTab = document.getElementById('login-tab');
    const regTab = document.getElementById('register-tab');

    // Hide all
    [loginForm, regForm, forgotForm].forEach(f => {
        if(f) {
            f.classList.add('fade-out');
            f.classList.remove('fade-in');
            setTimeout(() => f.style.display = 'none', 300); 
        }
    });

    // Reset Tabs
    if(loginTab) loginTab.className = "flex-1 py-3 text-sm font-semibold rounded-lg transition duration-300 text-slate-300 hover:text-white hover:bg-slate-700";
    if(regTab) regTab.className = "flex-1 py-3 text-sm font-semibold rounded-lg transition duration-300 text-slate-300 hover:text-white hover:bg-slate-700";

    let targetForm = null;
    
    if (type === 'login') {
        targetForm = loginForm;
        if(loginTab) loginTab.className = "flex-1 py-3 text-sm font-semibold rounded-lg transition duration-300 text-white bg-blue-600 shadow-md";
    } else if (type === 'register') {
        targetForm = regForm;
        if(regTab) regTab.className = "flex-1 py-3 text-sm font-semibold rounded-lg transition duration-300 text-white bg-teal-600 shadow-md";
    } else {
        targetForm = forgotForm;
    }

    if (targetForm) {
        setTimeout(() => {
            targetForm.style.display = 'block';
            // Force browser reflow to restart animation
            void targetForm.offsetWidth; 
            targetForm.classList.remove('fade-out');
            targetForm.classList.add('fade-in');
        }, 300);
    }
};

// 3. FORGOT PASSWORD LOGIC (The missing link)
window.sendCollegeResetOTP = async function() {
    console.log("Sending Reset OTP..."); // Debug log
    const emailInput = document.getElementById('fp-email');
    const email = emailInput.value.trim();

    if (!email) return window.setStatus("Please enter your registered email.", true);

    window.setLoading('fp-send-btn', true, "Sending...");

    try {
        const formData = new URLSearchParams();
        formData.append('email', email);
        
        const res = await fetch('/college/forgot-otp/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': window.getCSRFToken() 
            },
            body: formData
        });

        if (res.ok) {
            document.getElementById('fp-otp-section').classList.remove('hidden');
            emailInput.readOnly = true;
            window.setStatus("OTP Sent! Check your inbox.");
        } else {
            const data = await res.json();
            window.setStatus(data.error || "Email not found.", true);
        }
    } catch (e) {
        console.error(e);
        window.setStatus("Network Error", true);
    } finally {
        window.setLoading('fp-send-btn', false, "Resend");
    }
};

window.verifyCollegeResetOTP = async function() {
    const email = document.getElementById('fp-email').value;
    const otp = document.getElementById('fp-otp-input').value;

    if (otp.length < 4) return window.setStatus("Enter valid OTP", true);

    try {
        const res = await fetch('/college/forgot-verify/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': window.getCSRFToken() 
            },
            body: new URLSearchParams({ email, otp })
        });

        if (await res.text() === "VERIFIED") {
            document.getElementById('fp-otp-section').classList.add('hidden');
            document.getElementById('fp-newpass-section').classList.remove('hidden');
            window.setStatus("OTP Verified. Set new password.");
        } else {
            window.setStatus("Invalid OTP", true);
        }
    } catch (e) {
        window.setStatus("Verification Failed", true);
    }
};

window.finalizeCollegeReset = async function() {
    const pass = document.getElementById('fp-new-pass').value;
    const confirm = document.getElementById('fp-confirm-pass').value;

    if (pass.length < 8) return window.setStatus("Password must be at least 8 chars", true);
    if (pass !== confirm) return window.setStatus("Passwords do not match", true);

    window.setLoading('fp-reset-btn', true, "Updating...");

    try {
        const res = await fetch('/college/reset-pass/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': window.getCSRFToken() 
            },
            body: new URLSearchParams({ password: pass }) 
        });

        if (res.ok) {
            window.setStatus("Password Reset Successfully!");
            setTimeout(() => window.showForm('login'), 2000);
            
            // Reset UI
            document.getElementById('forgot-form').reset();
            document.getElementById('fp-newpass-section').classList.add('hidden');
            document.getElementById('fp-email').readOnly = false;
        } else {
            window.setStatus("Update failed", true);
        }
    } catch (e) {
        window.setStatus("Server Error", true);
    } finally {
        window.setLoading('fp-reset-btn', false, "Update Password");
    }
};

// 4. REGISTRATION LOGIC
let isEmailVerified = false;

window.sendCollegeOTP = async function() {
    const emailInput = document.getElementById('reg-email');
    const email = emailInput ? emailInput.value : '';
    
    if (!email || !email.includes('@')) return window.setStatus('Enter a valid email first', true);
    
    window.setLoading('send-otp-btn', true);
    
    try {
        const formData = new URLSearchParams();
        formData.append('email', email);
        formData.append('type', 'college_register'); 

        const res = await fetch('/send-otp/', { 
            method: 'POST',
            headers: { 
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': window.getCSRFToken() 
            },
            body: formData
        });
        
        if (res.ok) {
            document.getElementById('otp-section').classList.remove('hidden');
            if(emailInput) emailInput.readOnly = true;
            window.setStatus('OTP Sent to your email!');
        } else {
            window.setStatus('Failed to send OTP. Try again.', true);
        }
    } catch(e) { 
        window.setStatus('Network error', true); 
    }
    finally { 
        window.setLoading('send-otp-btn', false, "Resend"); 
    }
};

window.verifyCollegeOTP = async function() {
    const email = document.getElementById('reg-email').value;
    const otp = document.getElementById('otp-input').value;
    
    try {
        const res = await fetch('/verify-email-otp/', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': window.getCSRFToken() 
            },
            body: new URLSearchParams({ email, otp })
        });
        
        if (await res.text() === "VERIFIED") {
            isEmailVerified = true;
            document.getElementById('otp-section').classList.add('hidden');
            document.getElementById('send-otp-btn').style.display = 'none';
            const emailInput = document.getElementById('reg-email');
            emailInput.classList.add('border-green-500', 'text-green-400');
            window.setStatus('Email Verified Successfully!');
            window.validateCollegePassword(); // Update button state
        } else {
            window.setStatus('Invalid OTP. Check your inbox.', true);
        }
    } catch(e) {
        window.setStatus('Verification failed', true);
    }
};

window.validateCollegePassword = function() {
    const p1 = document.getElementById('reg-pass').value;
    const p2 = document.getElementById('reg-confirm-pass').value;
    const len = p1.length >= 8;
    const match = p1 === p2 && p1 !== '';
    
    const rLen = document.getElementById('rule-length');
    const rMatch = document.getElementById('rule-match');
    
    if(rLen) {
        rLen.innerHTML = len ? "✓ Min 8 characters" : "❌ Min 8 characters";
        rLen.className = len ? "text-green-400" : "text-red-400";
    }
    if(rMatch) {
        rMatch.innerHTML = match ? "✓ Passwords match" : "❌ Passwords match";
        rMatch.className = match ? "text-green-400" : "text-red-400";
    }
    
    const btn = document.getElementById('register-btn');
    if (btn) {
        if (isEmailVerified && len && match) {
            btn.disabled = false;
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
        } else {
            btn.disabled = true;
            btn.classList.add('opacity-50', 'cursor-not-allowed');
        }
    }
};

window.handleCollegeRegister = async function(e) {
    e.preventDefault();
    if (!isEmailVerified) return window.setStatus("Please verify email first", true);

    const website = document.getElementById('reg-college-website').value;
    // Basic regex check
    const urlPattern = new RegExp('^(https?:\\/\\/)?'+ '((([a-z\\d]([a-z\\d-]*[a-z\\d])*)\\.)+[a-z]{2,}|'+ '((\\d{1,3}\\.){3}\\d{1,3}))'+ '(\\:\\d+)?(\\/[-a-z\\d%_.~+]*)*'+ '(\\?[;&a-z\\d%_.~+=-]*)?'+ '(\\#[-a-z\\d_]*)?$','i');
    if (!urlPattern.test(website)) {
        return window.setStatus("Invalid Website URL", true);
    }

    window.setLoading('register-btn', true, "Registering...");

    const payload = new FormData();
    payload.append('college_name', document.getElementById('reg-college-name').value);
    payload.append('college_code', document.getElementById('reg-college-code').value);
    payload.append('website', website);
    payload.append('email', document.getElementById('reg-email').value);
    payload.append('password', document.getElementById('reg-pass').value);

    try {
        const res = await fetch('/college/register-api/', {
            method: 'POST',
            headers: { 'X-CSRFToken': window.getCSRFToken() },
            body: payload
        });

        const data = await res.json(); 

        if (res.ok) {
            if (data.message && data.message.includes("pending")) {
                const el = document.getElementById('status-message');
                if (el) {
                    el.innerHTML = `⚠️ ${data.message}`;
                    el.className = `p-3 rounded-lg text-sm text-center font-medium bg-amber-900/80 text-amber-200 border border-amber-700 shadow-lg`;
                    el.classList.remove('hidden', 'opacity-0');
                }
                document.getElementById('register-form').reset();
            } else {
                window.setStatus("Account Created! Redirecting to Login...");
                setTimeout(() => window.showForm('login'), 2000);
                document.getElementById('register-form').reset();
            }
        } else {
            window.setStatus(data.error || "Registration failed.", true);
        }
    } catch (err) {
        window.setStatus("Network Error", true);
    } finally {
        window.setLoading('register-btn', false);
    }
};

window.handleCollegeLogin = async function(e) {
    e.preventDefault();
    window.setLoading('login-btn', true, "Authenticating...");
    
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    
    try {
        const res = await fetch('/college/login-api/', { 
            method: 'POST',
            headers: { 
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-CSRFToken': window.getCSRFToken() 
            },
            body: new URLSearchParams({ email, password })
        });
        
        if (res.ok) {
            window.location.href = '/college/dashboard/'; 
        } else {
            window.setStatus("Invalid credentials", true);
            window.setLoading('login-btn', false);
        }
    } catch(err) {
        window.setStatus("Server Error", true);
        window.setLoading('login-btn', false);
    }
};

// 5. ANIMATIONS ON LOAD
document.addEventListener('DOMContentLoaded', function() {
    const titleEl = document.getElementById('app-title');
    if (titleEl) {
        const text = "Present Sir!!!";
        titleEl.innerHTML = '';
        text.split('').forEach((char, i) => {
            const span = document.createElement('span');
            span.textContent = char;
            span.style.opacity = '0';
            span.style.display = 'inline-block';
            span.style.animation = `type-in 0.3s cubic-bezier(0.4, 0, 0.2, 1) forwards ${i * 0.05}s`;
            if (char === ' ') span.style.width = '0.3em';
            titleEl.appendChild(span);
        });
    }
    
    // Initial Hide
    const reg = document.getElementById('register-form');
    const forgot = document.getElementById('forgot-form');
    if(reg) reg.style.display = 'none';
    if(forgot) forgot.style.display = 'none';
});