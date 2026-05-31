function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

function getCsrfToken() {
  // Try to get from cookie first
  let token = getCookie('csrftoken');
  if (token) return token;

  // Fallback: try to get from meta tag
  const metaTag = document.querySelector('meta[name="csrf-token"]');
  if (metaTag) {
    token = metaTag.getAttribute('content');
  }

  // Last fallback: try to get from hidden input
  if (!token) {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input) {
      token = input.value;
    }
  }

  return token || '';
}

// Application State
const appState = {
  currentUserId: 'user-001',
  activeClassId: null,
  currentClassData: null,
  classes: [],
  newClassData: {}, // Temporarily stores data between Step 1 and Step 2
  isOfflineMode: true
};

// DOM Elements
const elements = {
  // Navigation
  navMyClasses: document.getElementById('nav-my-classes'),
  navCreateClass: document.getElementById('nav-create-class'),
  navMenu: document.getElementById('nav-menu'),
  menuBtn: document.getElementById('menu-btn'),
  mobileMenu: document.getElementById('mobile-menu'),
  mobileNavBtns: document.querySelectorAll('.mobile-nav-btn'),

  // Sections
  myClassesSection: document.getElementById('my-classes-section'),
  classDetailSection: document.getElementById('class-detail-section'),
  menuSection: document.getElementById('menu-section'),
  dashboardMetricsView: document.getElementById('dashboard-metrics-view'),

  // Modals
  createClassModal: document.getElementById('create-class-modal'),
  addStudentsModal: document.getElementById('add-students-modal'),
  takeAttendanceModal: document.getElementById('take-attendance-modal'),

  // Buttons
  backToClasses: document.getElementById('back-to-classes'),
  takeAttendanceBtn: document.getElementById('take-attendance-btn'),
  viewDashboardBtn: document.getElementById('view-dashboard-btn'),
  downloadDataBtn: document.getElementById('download-data-btn'),
  addDummyClass: document.getElementById('add-dummy-class'),

  // Forms
  createClassForm: document.getElementById('create-class-form'),
  addStudentsForm: document.getElementById('add-students-form'),
  takeAttendanceForm: document.getElementById('take-attendance-form'),

  // Form controls
  totalStudents: document.getElementById('total-students'),
  totalHoursInput: document.getElementById('total-hours-input'),
  studentFieldsContainer: document.getElementById('student-fields-container'),
  studentCountDisplay: document.getElementById('student-count-display'),
  attendanceStudentList: document.getElementById('attendance-student-list'),
  attendanceDate: document.getElementById('attendance-date'),

  // Summary elements
  summaryTotal: document.getElementById('summary-total'),
  summaryPresent: document.getElementById('summary-present'),
  summaryAbsent: document.getElementById('summary-absent'),

  // Other
  classesList: document.getElementById('classes-list'),
  classDetailTitle: document.getElementById('class-detail-title'),
  attendanceHistoryView: document.getElementById('attendance-history-view'),
  statusMessage: document.getElementById('status-message'),
  loadingIndicator: document.getElementById('loading-indicator'),

  // Metrics
  metricTotalStudents: document.getElementById('metric-total-students'),
  metricTotalSessions: document.getElementById('metric-total-sessions'),
  metricTotalHours: document.getElementById('metric-total-hours')
};

// Utility Functions
const utils = {
  showStatus(message, isError = false) {
    const elem = elements.statusMessage;
    elem.textContent = message;
    elem.className = `fixed top-20 right-4 z-50 p-4 rounded-lg text-sm shadow-xl transition-opacity duration-300 ${isError ? 'bg-red-800/50 text-red-300' : 'bg-green-800/50 text-green-300'}`;
    elem.classList.remove('hidden', 'opacity-0');

    setTimeout(() => {
      elem.classList.add('opacity-100');
    }, 10);

    setTimeout(() => {
      elem.classList.remove('opacity-100');
      setTimeout(() => {
        elem.classList.add('hidden');
      }, 300);
    }, 5000);
  },

  formatDate(date) {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  },

  isValidDate(dateString) {
    const selectedDate = new Date(dateString);
    const today = new Date();
    const threeDaysAgo = new Date();
    threeDaysAgo.setDate(today.getDate() - 3);

    // Reset times for accurate comparison
    selectedDate.setHours(0, 0, 0, 0);
    today.setHours(0, 0, 0, 0);
    threeDaysAgo.setHours(0, 0, 0, 0);

    return selectedDate <= today && selectedDate >= threeDaysAgo;
  }
};

// Chart Management - Updated with OD Logic
const chartManager = {
  trendChartInstance: null,
  pieChartInstance: null,

  renderCharts: (classData) => {
    // 1. Destroy old charts
    if (chartManager.trendChartInstance) {
      chartManager.trendChartInstance.destroy();
      chartManager.trendChartInstance = null;
    }
    if (chartManager.pieChartInstance) {
      chartManager.pieChartInstance.destroy();
      chartManager.pieChartInstance = null;
    }

    // 2. Wait for transition
    setTimeout(() => {
      chartManager._draw(classData);
    }, 100);
  },

  _draw: (classData) => {
    const records = classData.attendanceRecords || [];

    // --- DATA PREP ---
    let labels = [], dataPoints = [];
    let totalP = 0, totalA = 0, totalOD = 0;

    // Calculate Totals for Pie Chart
    records.forEach(r => {
      totalP += r.presentCount;
      totalA += r.absentCount;
      totalOD += (r.odCount || 0); // Safety check if odCount is missing
    });

    // Prepare Trend Data
    if (records.length === 0) {
      labels = ['No Data'];
      dataPoints = [0];
    } else {
      // Get last 10 sessions
      const recent = [...records].reverse().slice(-10);
      labels = recent.map(r => {
        const d = new Date(r.date);
        return `${d.getDate()}/${d.getMonth() + 1}`;
      });

      // Calculate % for each day: (Present + OD) / Total
      dataPoints = recent.map(r => {
        if (r.total > 0) {
          const effectivePresent = r.presentCount + (r.odCount || 0);
          return Math.round((effectivePresent / r.total) * 100);
        }
        return 0;
      });
    }

    // --- DRAW TREND CHART ---
    const ctxTrend = document.getElementById('trendChart')?.getContext("2d");
    if (ctxTrend) {
      chartManager.trendChartInstance = new Chart(ctxTrend, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [{
            label: 'Attendance %',
            data: dataPoints,
            borderColor: '#20c997', // Teal
            backgroundColor: 'rgba(32, 201, 151, 0.2)',
            borderWidth: 2,
            pointBackgroundColor: '#fff',
            fill: true,
            tension: 0.3
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: {
              beginAtZero: true,
              max: 100,
              grid: { color: '#334155' }
            },
            x: { grid: { display: false } }
          }
        }
      });
    }

    // --- DRAW PIE CHART ---
    const ctxPie = document.getElementById('pieChart')?.getContext("2d");
    if (ctxPie) {
      // Check if data exists
      const hasData = (totalP > 0 || totalA > 0 || totalOD > 0);

      const pieData = hasData ? [totalP, totalOD, totalA] : [1];
      // Colors: Present(Teal), OD(Blue), Absent(Red), Empty(Grey)
      const pieColors = hasData ? ['#20c997', '#3b82f6', '#ef4444'] : ['#334155'];

      chartManager.pieChartInstance = new Chart(ctxPie, {
        type: 'doughnut',
        data: {
          labels: hasData ? ['Present', 'On Duty', 'Absent'] : ['No Data'],
          datasets: [{
            data: pieData,
            backgroundColor: pieColors,
            borderWidth: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '75%',
          plugins: {
            legend: {
              position: 'bottom',
              labels: { color: '#cbd5e1', font: { size: 11 } }
            }
          }
        }
      });
    }
  }
};
window.chartManager = chartManager;

// Navigation Functions
const navigation = {
  // Inside dashboard.js -> navigation object

  showSection(sectionId) {
    // 1. Hide all main sections (with safety checks)
    if (elements.myClassesSection) elements.myClassesSection.classList.add('hidden');
    if (elements.classDetailSection) elements.classDetailSection.classList.add('hidden');
    if (elements.menuSection) elements.menuSection.classList.add('hidden');

    // 2. THIS IS THE FIX: Check if dashboardMetricsView exists before touching it
    if (elements.dashboardMetricsView) {
      elements.dashboardMetricsView.classList.add('hidden');
    }

    // 3. Show the requested section
    const target = document.getElementById(`${sectionId}-section`);
    if (target) {
      target.classList.remove('hidden');
    } else {
      console.error(`Section not found: ${sectionId}-section`);
    }

    // 4. Hide mobile menu if open
    if (elements.mobileMenu) elements.mobileMenu.classList.add('hidden');
  },

  toggleMobileMenu() {
    const menu = elements.mobileMenu;
    if (menu.classList.contains('hidden')) {
      menu.classList.remove('hidden');
    } else {
      menu.classList.add('hidden');
    }
  },

  viewClassDetail(classId, classData) {
    appState.activeClassId = classId;
    appState.currentClassData = classData;
    elements.classDetailTitle.textContent = `${classData.className} - ${classData.subjectName}`;
    this.showSection('class-detail');
    this.loadAttendanceHistory();
  },

  loadAttendanceHistory() {
    const classData = appState.currentClassData;
    const history = classData.attendanceRecords || [];
    const container = elements.attendanceHistoryView; // Ensure this matches your HTML ID
    if (!container) return;

    let html = '<div class="space-y-3">';
    if (history.length === 0) {
      html += '<p class="text-slate-500 text-center">No attendance records found.</p>';
    } else {
      history.forEach(record => {
        const total = record.total || 0;
        const present = record.presentCount || 0;
        const od = record.odCount || 0;
        const percent = total > 0 ? Math.round(((present + od) / total) * 100) : 0;
        const attendancePercent = Math.round((record.presentCount / record.total) * 100);
        html += `
            <div class="bg-slate-800 p-4 rounded-lg border border-slate-700/50 hover:border-slate-600 transition">
                <div class="flex justify-between items-center">
                    <div>
                        <div class="flex items-center gap-2">
                            <h4 class="text-teal-400 font-semibold">${record.date}</h4>
                            <span class="text-xs text-slate-500 bg-slate-900 px-2 py-0.5 rounded border border-slate-700">
                                S: ${record.sessionDisplay || '1'}
                            </span>
                        </div>
                        <div class="text-sm text-slate-400 mt-1 space-x-2">
                            <span class="text-green-400">P: ${present}</span>
                            <span class="text-blue-400">OD: ${od}</span>
                            <span class="text-red-400">A: ${record.absentCount}</span>
                            <span class="text-slate-500">|</span>
                            <span class="font-bold text-white">${percent}%</span>
                        </div>
                    </div>
                    
                    <button class="text-blue-400 hover:text-blue-300 text-sm font-medium hover:underline" 
                            onclick="attendance.viewAttendanceDetail(${record.id})">
                        View Details
                    </button>
                </div>
            </div>
        `;
      });
    }
    html += '</div>';
    container.innerHTML = html;
    elements.attendanceHistoryView.innerHTML = html;
  },

  // Inside navigation object
  loadDashboardMetrics() {
    const classData = appState.currentClassData;
    if (!classData) return;

    const taken = classData.totalHoursTaken || 0;
    const planned = classData.totalHours || 45;

    if (document.getElementById('metric-total-hours')) {
      // Display: "24 / 45"
      document.getElementById('metric-total-hours').textContent = `${taken} / ${planned}`;
    }

    // 1. Update text stats
    if (document.getElementById('metric-total-students'))
      document.getElementById('metric-total-students').textContent = classData.students.length;

    if (document.getElementById('metric-total-sessions'))
      document.getElementById('metric-total-sessions').textContent = taken;

    if (document.getElementById('metric-total-hours'))
      document.getElementById('metric-total-hours').textContent = `${taken} / ${planned}`;

    // 2. SHOW THE MODAL
    const modal = document.getElementById('metrics-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    // Refresh Icons inside modal
    if (window.lucide) lucide.createIcons();

    // 3. Render Charts 
    // We add a delay to ensure the modal animation is done and canvas has size
    setTimeout(() => {
      if (window.chartManager) {
        chartManager.renderCharts(classData);
      }
    }, 150);
  },
};

// Class Management
const classManager = {
  generateStudentFields(count, container, totalStudentsDisplay) {
    const num = Math.max(1, parseInt(count) || 1);
    container.innerHTML = '';
    if (totalStudentsDisplay) totalStudentsDisplay.textContent = num;

    for (let i = 1; i <= num; i++) {
      const div = document.createElement('div');
      div.className = 'grid grid-cols-12 gap-2 pb-2 border-b border-slate-700/50 mb-2';

      div.innerHTML = `
            <div class="col-span-3">
                <input type="text" required 
                       class="student-regno w-full px-2 py-1 bg-slate-700 text-white border border-slate-600 rounded text-sm placeholder-slate-400" 
                       placeholder="Reg No *">
            </div>
            <div class="col-span-4">
                <input type="text" required 
                       class="student-name w-full px-2 py-1 bg-slate-700 text-white border border-slate-600 rounded text-sm placeholder-slate-400" 
                       placeholder="Name *">
            </div>
            <div class="col-span-5">
                <input type="email" 
                       class="student-email w-full px-2 py-1 bg-slate-700 text-white border border-slate-600 rounded text-sm placeholder-slate-500" 
                       placeholder="Email (Optional)">
            </div>
        `;
      container.appendChild(div);
    }
  },

  startCreateClassStep2() {
    const className = document.getElementById('class-name').value.trim();
    const subjectName = document.getElementById('subject-name').value.trim();
    const subjectCode = document.getElementById('subject-code').value.trim();
    const totalStudents = parseInt(elements.totalStudents.value);
    const totalHours = parseInt(elements.totalHoursInput.value);

    if (!className || !subjectName || totalStudents < 1 || totalHours < 1) {
      utils.showStatus('Please fill in all required fields correctly (Step 1)', true);
      return;
    }

    // Store intermediate data
    appState.newClassData = { className, subjectName, subjectCode, totalStudents, totalHours };

    modals.hideCreateClassModal();
    modals.showAddStudentsModal(totalStudents);
  },

  async finishCreateClass() {
    // 1. Collect Student Data from Inputs
    const students = [];
    const regnoInputs = elements.studentFieldsContainer.querySelectorAll('.student-regno');
    const nameInputs = elements.studentFieldsContainer.querySelectorAll('.student-name');
    const emailInputs = elements.studentFieldsContainer.querySelectorAll('.student-email')

    for (let i = 0; i < regnoInputs.length; i++) {
      if (!regnoInputs[i].value.trim() || !nameInputs[i].value.trim()) {
        utils.showStatus(`Please fill in Reg No. and Name for student ${i + 1}`, true);
        return;
      }
      students.push({
        regNo: regnoInputs[i].value.trim(),
        name: nameInputs[i].value.trim(),
        email: emailInputs[i].value.trim()
      });
    }

    // 2. Prepare Data Payload
    const payload = {
      className: appState.newClassData.className,
      subjectName: appState.newClassData.subjectName,
      subjectCode: appState.newClassData.subjectCode,
      totalHours: appState.newClassData.totalHours,
      students: students
    };

    // 3. Send to Django (API Call)
    utils.showStatus('Saving class to database...');

    try {
      const response = await fetch(window.djangoUrls.createClass, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        // Success! Reload data from DB to see the new class
        modals.hideAddStudentsModal();
        appState.newClassData = {};

        await this.fetchClassesFromDB(); // Refresh the list

        utils.showStatus('Class created successfully!');
      } else {
        const err = await response.json();
        utils.showStatus('Error: ' + (err.error || 'Failed to save'), true);
      }

    } catch (e) {
      console.error(e);
      utils.showStatus('Network error occurred', true);
    }
  },

  // REPLACES THE OLD loadClassesFromStorage
  async fetchClassesFromDB() {
    // Show loading spinner
    if (elements.loadingIndicator) elements.loadingIndicator.classList.remove('hidden');

    try {
      const response = await fetch(window.djangoUrls.dashboardData);

      if (response.status === 401) {
        // Not logged in, redirect to login
        window.location.href = "/psapp/login/";
        return;
      }

      const data = await response.json();

      // Update App State with Database Data
      appState.classes = data.classes;

      if (data.faculty_photo) {
        const img = document.getElementById('menu-profile-photo');
        const initialsDiv = document.getElementById('menu-profile-initials');

        if (img) {
          img.src = data.faculty_photo;
          img.classList.remove('hidden'); // Show Image
        }
        if (initialsDiv) {
          initialsDiv.classList.add('hidden'); // Hide Initials
        }
      }

      // Refresh the UI
      this.renderClasses();
      utils.showStatus('Data loaded from database');

    } catch (error) {
      console.error('Error fetching data:', error);
      utils.showStatus('Error loading data', true);
    } finally {
      // Hide spinner
      if (elements.loadingIndicator) elements.loadingIndicator.classList.add('hidden');
    }
  },

  renderClasses() {
    const container = elements.classesList;

    // 1. Try to get the 'no-classes' element
    let noClasses = document.getElementById('no-classes');

    // 2. SAFETY FIX: Detach it from the DOM so we don't destroy it when clearing the container
    if (noClasses) {
      noClasses.remove();
    }

    // 3. Clear the container (removes old class cards)
    container.innerHTML = '';

    // 4. Put 'no-classes' back into the container (hidden or shown)
    if (noClasses) {
      container.appendChild(noClasses);

      if (appState.classes.length === 0) {
        noClasses.classList.remove('hidden');
      } else {
        noClasses.classList.add('hidden');
      }
    }

    // 5. Render the Class Cards
    appState.classes.forEach(cls => {
      const card = document.createElement('div');
      card.className = 'class-card bg-slate-800 rounded-xl p-6 space-y-3 shadow-lg border border-slate-700 hover:border-teal-500 cursor-pointer transition';
      let badgeHTML = '';
      if (cls.isAssigned) {
        // Official Badge (Teal/Blue)
        badgeHTML = `<span class="absolute top-0 right-0 bg-teal-600/90 text-white text-[10px] uppercase font-bold px-3 py-1 rounded-bl-lg shadow-sm">Official</span>`;
      } else {
        // Personal Badge (Purple/Gray)
        badgeHTML = `<span class="absolute top-0 right-0 bg-purple-600/90 text-white text-[10px] uppercase font-bold px-3 py-1 rounded-bl-lg shadow-sm">Personal</span>`;
      }

      // Add Click Event
      card.onclick = () => navigation.viewClassDetail(cls.id, cls);

      // Card Content
      card.innerHTML = `
        ${badgeHTML}<div class="flex justify-between items-start">
        <p class="text-sm font-medium text-teal-400">${cls.subjectCode || 'N/A'}</p>
        <p class="text-xs text-slate-500">${cls.createdAt || ''}</p> 
        </div>
        <h3 class="text-2xl font-bold text-white mt-1">${cls.className}</h3>
        <p class="text-slate-400">${cls.subjectName}</p>
        <div class="flex justify-between text-sm text-slate-500 pt-2 border-t border-slate-700 mt-3">
        <span>Students: ${cls.students.length}</span>
        <span>Sessions: ${(cls.attendanceRecords || []).length}</span>
        </div>
      `;

      container.appendChild(card);
    });
  },
};

// Attendance Management
// Inside dashboard.js - Replace the entire attendance object
// attendance management
const attendance = {
  // 1. RENDER ROSTER
  renderAttendanceRoster(students) {
    const container = document.getElementById('attendance-student-list');
    if (!container) return;

    container.innerHTML = '';

    if (!students || students.length === 0) {
      container.innerHTML = `
        <div class="text-center py-8 flex flex-col items-center justify-center">
            <p class="text-slate-400 font-medium">No students enrolled</p>
        </div>`;
      return;
    }

    students.forEach((student, index) => {
      const div = document.createElement('div');
      div.className = 'flex items-center justify-between p-3 bg-slate-800/50 hover:bg-slate-800 border border-slate-700 rounded-lg transition mb-2 group';

      div.innerHTML = `
            <div class="flex items-center gap-3">
                <span class="font-mono text-teal-400 text-xs font-bold bg-teal-900/20 px-2 py-1 rounded border border-teal-900/30">${student.regNo}</span>
                <span class="text-slate-200 font-medium text-sm group-hover:text-white transition">${student.name}</span>
            </div>
            
            <button type="button" 
                    id="btn-status-${index}" 
                    data-index="${index}" 
                    data-reg="${student.regNo}"
                    data-status="Present"
                    class="status-toggle-btn w-24 py-1.5 rounded-md font-bold text-[11px] uppercase tracking-wider bg-green-900/40 text-green-400 border border-green-700/50 shadow-sm transition-all hover:scale-105 active:scale-95">
                Present
            </button>
        `;
      container.appendChild(div);
    });

    document.querySelectorAll('.status-toggle-btn').forEach(btn => {
      btn.addEventListener('click', (e) => this.toggleStatus(e.target));
    });

    this.updateSummary();
  },

  // 2. TOGGLE STATUS
  toggleStatus(btn) {
    const current = btn.dataset.status;

    if (current === 'Present') {
      btn.dataset.status = 'Absent';
      btn.textContent = 'Absent';
      btn.className = 'status-toggle-btn w-24 py-1.5 rounded-md font-bold text-[11px] uppercase tracking-wider bg-red-900/40 text-red-400 border border-red-700/50 shadow-sm transition-all hover:scale-105 active:scale-95';
    } else if (current === 'Absent') {
      btn.dataset.status = 'OD';
      btn.textContent = 'On Duty';
      btn.className = 'status-toggle-btn w-24 py-1.5 rounded-md font-bold text-[11px] uppercase tracking-wider bg-blue-900/40 text-blue-400 border border-blue-700/50 shadow-sm transition-all hover:scale-105 active:scale-95';
    } else {
      btn.dataset.status = 'Present';
      btn.textContent = 'Present';
      btn.className = 'status-toggle-btn w-24 py-1.5 rounded-md font-bold text-[11px] uppercase tracking-wider bg-green-900/40 text-green-400 border border-green-700/50 shadow-sm transition-all hover:scale-105 active:scale-95';
    }
    this.updateSummary();
  },

  // 3. VIEW HISTORY DETAIL
  viewAttendanceDetail(sessionId) {
    const classData = appState.currentClassData;
    if (!classData.attendanceRecords) return;

    // Find Record by ID
    const history = classData.attendanceRecords;
    const currentIndex = history.findIndex(r => r.id === sessionId);

    if (currentIndex === -1) return;

    const record = history[currentIndex];
    const nextRecord = history[currentIndex - 1]; // Newer
    const prevRecord = history[currentIndex + 1]; // Older

    // Calculate Percent
    const total = record.total || 0;
    const effectivePresent = (record.presentCount || 0) + (record.odCount || 0);
    const percent = total > 0 ? Math.round((effectivePresent / total) * 100) : 0;

    let html = `
        <div class="bg-slate-800 rounded-lg p-4 border border-slate-700 animate-fade-in">
            <div class="flex justify-between items-center mb-6">
                <button id="btn-back-history" class="text-sm text-teal-400 hover:text-white flex items-center transition">
                    <i data-lucide="arrow-left" class="mr-1 h-4 w-4"></i> Back list
                </button>

                <div class="flex items-center space-x-2 bg-slate-900 rounded-lg p-1 border border-slate-700">
                    <button id="btn-prev-day" class="p-1 rounded hover:bg-slate-700 transition ${!prevRecord ? 'opacity-30 cursor-not-allowed' : 'text-teal-400'}" ${!prevRecord ? 'disabled' : ''}>
                        <i data-lucide="chevron-left" class="h-5 w-5"></i>
                    </button>
                    
                    <div class="text-center px-2">
                        <span class="block text-sm font-bold text-white">${record.date}</span>
                        <span class="block text-[10px] text-slate-500 uppercase tracking-wider">Session ${record.sessionDisplay || '1'}</span>
                    </div>

                    <button id="btn-next-day" class="p-1 rounded hover:bg-slate-700 transition ${!nextRecord ? 'opacity-30 cursor-not-allowed' : 'text-teal-400'}" ${!nextRecord ? 'disabled' : ''}>
                        <i data-lucide="chevron-right" class="h-5 w-5"></i>
                    </button>
                </div>

                <button onclick="attendance.editSession(${record.id})" class="bg-slate-700 hover:bg-slate-600 text-white text-xs px-3 py-1.5 rounded border border-slate-500 transition">
                    Edit
                </button>
            </div>

            <div class="grid grid-cols-4 gap-2 mb-6">
                 <div class="bg-slate-900 p-2 rounded border border-slate-700 text-center">
                    <p class="text-[10px] text-slate-400 uppercase">Total</p>
                    <p class="text-lg font-bold text-white">${total}</p>
                </div>
                <div class="bg-green-900/20 p-2 rounded border border-green-900/50 text-center">
                    <p class="text-[10px] text-green-400 uppercase">Present</p>
                    <p class="text-lg font-bold text-green-400">${record.presentCount}</p>
                </div>
                 <div class="bg-blue-900/20 p-2 rounded border border-blue-900/50 text-center">
                    <p class="text-[10px] text-blue-400 uppercase">OD</p>
                    <p class="text-lg font-bold text-blue-400">${record.odCount || 0}</p>
                </div>
                <div class="bg-red-900/20 p-2 rounded border border-red-900/50 text-center">
                    <p class="text-[10px] text-red-400 uppercase">Absent</p>
                    <p class="text-lg font-bold text-red-400">${record.absentCount}</p>
                </div>
            </div>
            
            <div class="space-y-2 max-h-96 overflow-y-auto custom-scroll pr-1">
    `;

    if (record.records && record.records.length > 0) {
      record.records.forEach(student => {
        let badgeClass = 'bg-slate-700 text-slate-300 border-slate-600';
        if (student.status === 'Present') badgeClass = 'bg-green-900/40 text-green-400 border-green-800';
        else if (student.status === 'Absent') badgeClass = 'bg-red-900/40 text-red-400 border-red-800';
        else if (student.status === 'OD') badgeClass = 'bg-blue-900/40 text-blue-400 border-blue-800';

        html += `
                <div class="flex justify-between items-center p-2.5 bg-slate-900/50 rounded-lg border border-slate-700/50">
                    <div class="flex items-center gap-3">
                        <span class="font-mono text-teal-500 text-xs bg-teal-900/10 px-1.5 py-0.5 rounded">${student.regNo}</span>
                        <span class="text-slate-300 text-sm">${student.name}</span>
                    </div>
                    <span class="px-2 py-0.5 rounded text-[10px] uppercase font-bold border ${badgeClass}">
                        ${student.status}
                    </span>
                </div>
            `;
      });
    } else {
      html += '<p class="text-slate-500 italic text-center py-4 text-sm">Detailed data unavailable.</p>';
    }

    html += '</div></div>';
    elements.attendanceHistoryView.innerHTML = html;
    if (window.lucide) lucide.createIcons();

    document.getElementById('btn-back-history').addEventListener('click', () => {
      navigation.loadAttendanceHistory();
    });

    const prevBtn = document.getElementById('btn-prev-day');
    if (prevBtn && !prevBtn.disabled) {
      prevBtn.addEventListener('click', () => this.viewAttendanceDetail(prevRecord.id));
    }
    const nextBtn = document.getElementById('btn-next-day');
    if (nextBtn && !nextBtn.disabled) {
      nextBtn.addEventListener('click', () => this.viewAttendanceDetail(nextRecord.id));
    }
  },

  // 4. UPDATE SUMMARY COUNTS
  updateSummary() {
    const list = document.getElementById('attendance-student-list');
    if (!list) return;
    let present = 0, absent = 0, od = 0;

    list.querySelectorAll('.status-toggle-btn').forEach(btn => {
      const status = btn.dataset.status;
      if (status === 'Present') present++;
      else if (status === 'Absent') absent++;
      else if (status === 'OD') od++;
    });

    if (document.getElementById('summary-present')) document.getElementById('summary-present').textContent = present;
    if (document.getElementById('summary-absent')) document.getElementById('summary-absent').textContent = absent;
    if (document.getElementById('summary-od')) document.getElementById('summary-od').textContent = od;
    const total = present + absent + od;
    if (document.getElementById('summary-total')) document.getElementById('summary-total').textContent = total;
  },

  // 5. SAVE ATTENDANCE (Updated with sessionId injection)
  async saveAttendance() {
    const date = document.getElementById('attendance-date').value;
    const startSess = document.getElementById('session-start').value;
    const endSess = document.getElementById('session-end').value;

    if (!date) { utils.showStatus('Please select a date', true); return; }
    if (parseInt(startSess) > parseInt(endSess)) {
      utils.showStatus("Start session cannot be greater than End session", true);
      return;
    }

    const btns = document.querySelectorAll('.status-toggle-btn');
    if (btns.length === 0) {
      utils.showStatus("No students to save!", true);
      return;
    }

    const attendanceRecords = [];
    btns.forEach(btn => {
      attendanceRecords.push({ regNo: btn.dataset.reg, status: btn.dataset.status });
    });

    // Check Mode
    const saveBtn = document.getElementById('save-attendance-btn');
    const isEditMode = saveBtn.dataset.mode === 'edit';
    const url = isEditMode ? window.djangoUrls.updateAttendance : window.djangoUrls.saveAttendance;

    const payload = {
      classId: appState.activeClassId,
      date: date,
      startSession: startSess,
      endSession: endSess,
      records: attendanceRecords
    };

    // <--- FIX: INJECT SESSION ID IF EDITING --->
    if (isEditMode) {
      payload.sessionId = saveBtn.dataset.sessionId;
    }

    utils.showStatus(isEditMode ? 'Updating session...' : 'Saving attendance...');

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(payload)
      });

      const result = await response.json();

      if (response.ok) {
        modals.hideTakeAttendanceModal();
        utils.showStatus(isEditMode ? 'Session Updated!' : 'Attendance Saved!');

        // Reset UI
        saveBtn.dataset.mode = '';
        saveBtn.dataset.sessionId = '';
        saveBtn.textContent = 'Save Attendance';
        document.getElementById('attendance-date').disabled = false;

        await classManager.fetchClassesFromDB();

        const updatedClass = appState.classes.find(c => c.id === appState.activeClassId);
        if (updatedClass) navigation.viewClassDetail(updatedClass.id, updatedClass);
      } else {
        utils.showStatus('Error: ' + (result.error || 'Failed'), true);
      }
    } catch (e) {
      console.error(e);
      utils.showStatus('Network error occurred', true);
    }
  },

  // 6. EDIT SESSION (Corrected Signature)
  editSession(sessionId) {
    const classData = appState.currentClassData;
    // Fix: Find session by ID, not by undefined variable
    const session = classData.attendanceRecords.find(r => r.id === sessionId);
    if (!session) return;

    modals.showTakeAttendanceModal();

    // Setup Edit UI
    const modal = document.getElementById('take-attendance-modal');
    modal.querySelector('h2').textContent = `Edit Attendance: ${session.date}`; // Use session.date

    // Fix: Set the value using the session's date
    const dateInput = document.getElementById('attendance-date');
    dateInput.value = session.date;
    dateInput.disabled = true;

    // Parse Session Numbers
    if (session.sessionDisplay) {
      const parts = session.sessionDisplay.split('-');
      document.getElementById('session-start').value = parts[0];
      document.getElementById('session-end').value = parts.length > 1 ? parts[1] : parts[0];
    }

    const saveBtn = document.getElementById('save-attendance-btn');
    saveBtn.dataset.sessionId = session.id;
    saveBtn.textContent = "Update Session";
    saveBtn.dataset.mode = 'edit';

    // Map existing statuses
    const statusMap = {};
    if (session.records) {
      session.records.forEach(r => statusMap[r.regNo] = r.status);
    }

    // Apply statuses to buttons
    const studentButtons = document.querySelectorAll('.status-toggle-btn');
    studentButtons.forEach(btn => {
      const reg = btn.dataset.reg;
      const pastStatus = statusMap[reg] || 'Absent';

      btn.dataset.status = pastStatus;
      btn.textContent = pastStatus === 'OD' ? 'On Duty' : pastStatus;

      // Update color class manually
      btn.className = 'status-toggle-btn w-24 py-1.5 rounded-md font-bold text-[11px] uppercase tracking-wider transition-all border shadow-sm ';
      if (pastStatus === 'Present') btn.classList.add('bg-green-900/40', 'text-green-400', 'border-green-700/50');
      else if (pastStatus === 'Absent') btn.classList.add('bg-red-900/40', 'text-red-400', 'border-red-700/50');
      else if (pastStatus === 'OD') btn.classList.add('bg-blue-900/40', 'text-blue-400', 'border-blue-700/50');
    });

    this.updateSummary();
  },

  downloadAttendanceData() {
    const classId = appState.activeClassId;
    if (!classId) { utils.showStatus('No class selected', true); return; }
    if (window.reportManager != 'undefined') reportManager.openModal();
    else {
      let url = window.djangoUrls.exportCsv.replace('0', classId);
      window.location.href = url;
    }
  }
};

// Modal Management
const modals = {
  showCreateClassModal() {
    elements.createClassModal.classList.remove('hidden');
    elements.createClassModal.classList.add('flex');
    elements.createClassForm.reset();
    elements.totalStudents.value = 1;
    elements.totalHoursInput.value = 45;
  },

  hideCreateClassModal() {
    elements.createClassModal.classList.add('hidden');
    elements.createClassModal.classList.remove('flex');
  },

  showAddStudentsModal(count) {
    elements.addStudentsModal.classList.remove('hidden');
    elements.addStudentsModal.classList.add('flex');
    classManager.generateStudentFields(count, elements.studentFieldsContainer, elements.studentCountDisplay);
  },

  hideAddStudentsModal() {
    elements.addStudentsModal.classList.add('hidden');
    elements.addStudentsModal.classList.remove('flex');
    elements.addStudentsForm.reset();
    elements.studentFieldsContainer.innerHTML = '';
  },

  async showTakeAttendanceModal() {
    if (!appState.currentClassData) {
      utils.showStatus('No class selected', true);
      return;
    }

    // 1. Show Modal
    const modal = document.getElementById('take-attendance-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    // 2. Reset Title (In case it was changed by Edit Session)
    const title = modal.querySelector('h2');
    if (title) title.textContent = "Take Attendance";

    // 3. Reset Button
    const saveBtn = document.getElementById('save-attendance-btn');
    if (saveBtn) {
      saveBtn.textContent = "Save Session";
      saveBtn.dataset.mode = "new";
    }

    // 4. Set Date (Safely)
    const today = utils.formatDate(new Date());
    const dateInput = document.getElementById('attendance-date');
    if (dateInput) {
      dateInput.value = today;
      dateInput.disabled = false;
    }

    // 5. Reset Feedback (Safely - THIS CAUSED YOUR ERROR)
    const feedback = document.getElementById('date-feedback');
    if (feedback) {
      feedback.textContent = '';
    }

    // 6. Reset Session Inputs
    if (document.getElementById('session-start')) document.getElementById('session-start').value = 1;
    if (document.getElementById('session-end')) document.getElementById('session-end').value = 1;

    try {
      const courseId = appState.activeClassId;
      const res = await fetch(`/api/get-suggested-session/?course_id=${courseId}&date=${today}`); // Make sure to add this URL to window.djangoUrls
      const data = await res.json();

      if (data.found) {
        document.getElementById('session-start').value = data.start;
        document.getElementById('session-end').value = data.end;
        utils.showStatus(data.message); // "Timetable found: Period 1-2"
      }
    } catch (e) { console.log("Auto-fill skipped"); }
    // 7. Render Student List
    attendance.renderAttendanceRoster(appState.currentClassData.students);
    attendance.updateSummary();
  },

  hideTakeAttendanceModal() {
    const modal = document.getElementById('take-attendance-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    document.getElementById('take-attendance-form').reset();
  }
};
// Student Management
const studentManager = {
  // Open the roster list
  openRoster() {
    const classData = appState.currentClassData;
    if (!classData) return;

    const container = document.getElementById('roster-list-container');
    container.innerHTML = '';
    const modal = document.getElementById('manage-students-modal');

    // Render List
    this.renderList(classData.students);

    modal.classList.remove('hidden');
    modal.classList.add('flex');
  },

  // Render the list (separated so search can use it too)
  // Inside studentManager object in dashboard.js

  renderList(students) {
    const container = document.getElementById('roster-list-container');
    container.innerHTML = '';

    if (!students || students.length === 0) {
      container.innerHTML = `
            <div class="flex flex-col items-center justify-center h-full text-slate-500 mt-10">
                <i data-lucide="users" class="w-12 h-12 mb-3 opacity-20"></i>
                <p>No students found.</p>
            </div>
        `;
      if (window.lucide) lucide.createIcons();
      return;
    }

    students.forEach(student => {
      // 1. Create Initials for Avatar (e.g. "John Doe" -> "JD")
      const initials = student.name
        .split(' ')
        .map(n => n[0])
        .join('')
        .substring(0, 2)
        .toUpperCase();

      // 2. Create Row Element
      const div = document.createElement('div');
      div.className = "group flex items-center justify-between p-3 bg-slate-700/30 hover:bg-slate-700/60 border border-slate-700/50 rounded-xl transition-all cursor-pointer";

      // 3. Set Inner HTML
      div.innerHTML = `
            <div class="flex items-center gap-4 flex-1" onclick="studentManager.viewProfile(${student.id})">
                <div class="w-10 h-10 rounded-full bg-teal-900/50 text-teal-400 border border-teal-500/30 flex items-center justify-center font-bold text-sm shadow-sm">
                    ${initials}
                </div>
                
                <div>
                    <h4 class="text-white font-medium group-hover:text-teal-300 transition">${student.name}</h4>
                    <p class="text-slate-400 text-xs font-mono">${student.regNo}</p>
                </div>
            </div>

            <button class="edit-student-trigger p-2 text-slate-400 hover:text-white hover:bg-purple-600 rounded-lg transition" 
                    title="Edit Details"
                    data-id="${student.id}" 
                    data-reg="${student.regNo}" 
                    data-name="${student.name}">
                <i data-lucide="pencil" class="w-4 h-4"></i>
            </button>
        `;
      container.appendChild(div);
    });

    // 4. Re-initialize Icons & Listeners
    if (window.lucide) lucide.createIcons();

    document.querySelectorAll('.edit-student-trigger').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation(); // Stop click from opening profile
        this.openEditForm(btn.dataset.id, btn.dataset.reg, btn.dataset.name);
      });
    });
  },

  // NEW FUNCTION: Fetch and Show Profile
  // In dashboard.js inside studentManager object

  async viewProfile(studentId) {
    utils.showStatus('Fetching student profile...');
    const url = window.djangoUrls.getStudentStats.replace('0', studentId);

    try {
      const response = await fetch(url);
      const data = await response.json();

      if (response.ok) {
        // 1. Text Data
        document.getElementById('profile-name').textContent = data.name;
        document.getElementById('profile-reg').textContent = data.regNo;
        document.getElementById('profile-class').textContent = `${data.course} - ${data.subject}`;

        // 2. Initials
        const initials = data.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
        document.getElementById('profile-initials').textContent = initials;

        // 3. Stats (UPDATED WITH OD)
        document.getElementById('profile-total').textContent = data.total;
        document.getElementById('profile-present').textContent = data.present;
        document.getElementById('profile-absent').textContent = data.absent;
        document.getElementById('profile-percent').textContent = data.percentage + '%';

        // --- NEW LINE: Update OD Count ---
        if (document.getElementById('profile-od')) {
          document.getElementById('profile-od').textContent = data.od || 0;
        }

        // 4. Status Badge & Color Theme
        const badge = document.getElementById('profile-status-badge');
        const pic = document.getElementById('profile-pic-placeholder');
        badge.textContent = data.statusLabel;

        // Reset Base Classes
        badge.className = "px-4 py-1 rounded-full text-sm font-bold border";
        pic.className = "w-20 h-20 bg-slate-700 rounded-full mx-auto flex items-center justify-center mb-3 shadow-inner border-2";

        if (data.statusColor === 'green') {
          badge.classList.add('bg-green-900', 'text-green-400', 'border-green-700');
          pic.classList.add('border-green-500');
        } else if (data.statusColor === 'amber') {
          badge.classList.add('bg-amber-900', 'text-amber-400', 'border-amber-700');
          pic.classList.add('border-amber-500');
        } else {
          badge.classList.add('bg-red-900', 'text-red-400', 'border-red-700');
          pic.classList.add('border-red-500');
        }

        // 5. Calculator Logic
        const resultBox = document.getElementById('skip-calc-result');
        const present = parseInt(data.present) || 0;
        const od = parseInt(data.od) || 0;
        const total = parseInt(data.total) || 0;

        // Effective Present includes OD
        const effectivePresent = present + od;
        const targetPct = 0.75;
        const currentPct = total > 0 ? effectivePresent / total : 0;

        if (currentPct >= targetPct) {
          const maxTotal = effectivePresent / targetPct;
          const buffer = Math.floor(maxTotal - total);
          if (buffer > 0) {
            resultBox.innerHTML = `<span class="text-green-400 font-bold">Safe Zone.</span><br>Student can skip <span class="text-white font-bold text-lg">${buffer}</span> more classes.`;
          } else {
            resultBox.innerHTML = `<span class="text-amber-400">Safe, but on the edge. Cannot miss any classes.</span>`;
          }
        } else {
          const needed = Math.ceil((3 * total) - (4 * effectivePresent));
          resultBox.innerHTML = `<span class="text-red-400 font-bold">Danger Zone.</span><br>Must attend <span class="text-white font-bold text-lg">${Math.max(1, needed)}</span> consecutive classes.`;
        }

        // Show Modal
        const modal = document.getElementById('student-profile-modal');
        modal.classList.remove('hidden');
        modal.classList.add('flex');
      } else {
        utils.showStatus('Error fetching profile', true);
      }
    } catch (e) {
      console.error(e);
      utils.showStatus('Network error', true);
    }
  },

  // Open the small edit form
  async openEditForm(id, regNo, name) {
    document.getElementById('edit-student-id').value = id;
    document.getElementById('edit-student-reg').value = regNo;
    document.getElementById('edit-student-name').value = name;

    // Fetch email from backend to pre-fill it
    document.getElementById('edit-student-email').value = ""; // Clear first
    try {
      const url = window.djangoUrls.getStudentStats.replace('0', id);
      const res = await fetch(url);
      const data = await res.json();
      if (res.ok) {
        document.getElementById('edit-student-email').value = data.email || '';
      }
    } catch (e) { console.log("Could not fetch email"); }

    // Show Modal
    const modal = document.getElementById('edit-student-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
  },

  async closeEditForm() {
    const modal = document.getElementById('edit-student-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    // Clear form
    document.getElementById('edit-student-form').reset();
  },

  // Filter list based on search input
  filterRoster(query) {
    const classData = appState.currentClassData;
    if (!classData) return;
    const lowerQ = query.toLowerCase();

    const filtered = classData.students.filter(s =>
      s.name.toLowerCase().includes(lowerQ) ||
      s.regNo.toLowerCase().includes(lowerQ)
    );
    this.renderList(filtered);
  },
  // Submit API Call
  async saveStudentChange() {
    const id = document.getElementById('edit-student-id').value;
    const name = document.getElementById('edit-student-name').value;
    const regNo = document.getElementById('edit-student-reg').value;
    const email = document.getElementById('edit-student-email').value; // <--- Get Email

    try {
      const response = await fetch(window.djangoUrls.editStudent, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
          student_id: id,
          name: name,
          regNo: regNo,
          email: email // <--- Send Email
        })
      });

      if (response.ok) {
        utils.showStatus('Student updated successfully!');
        this.closeEditForm();

        // Update local list visual (Email isn't shown in list, so just name/reg)
        const classData = appState.currentClassData;
        const studentIndex = classData.students.findIndex(s => s.id == id);
        if (studentIndex !== -1) {
          classData.students[studentIndex].name = name;
          classData.students[studentIndex].regNo = regNo;
        }
        this.openRoster();
      } else {
        utils.showStatus('Failed to update student', true);
      }
    } catch (e) {
      console.error(e);
      utils.showStatus('Network error', true);
    }
  }
};

const setupEventListeners = () => {
  const safeAdd = (id, evt, fn) => {
    const el = typeof id === 'string' ? document.getElementById(id) : id;
    if (el) el.addEventListener(evt, fn);
  };

  // 1. Navigation
  safeAdd('nav-my-classes', 'click', () => navigation.showSection('my-classes'));
  safeAdd('nav-create-class', 'click', () => modals.showCreateClassModal());
  safeAdd('nav-menu', 'click', () => navigation.showSection('menu'));
  safeAdd('menu-btn', 'click', navigation.toggleMobileMenu);
  safeAdd('back-to-classes', 'click', () => navigation.showSection('my-classes'));

  // 2. Mobile Nav Buttons
  document.querySelectorAll('.mobile-nav-item').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const target = e.currentTarget.dataset.target;
      if (target === 'create-class') modals.showCreateClassModal();
      else navigation.showSection(target);
    });
  });

  document.querySelectorAll('.mobile-nav-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const target = e.currentTarget.dataset.target;
      if (target === 'create-class') modals.showCreateClassModal();
      else navigation.showSection(target);
      navigation.toggleMobileMenu();
    });
  });

  // 3. Class Action Buttons
  safeAdd('take-attendance-btn', 'click', modals.showTakeAttendanceModal);
  safeAdd('view-dashboard-btn', 'click', navigation.loadDashboardMetrics);
  safeAdd('download-data-btn', 'click', attendance.downloadAttendanceData);
  safeAdd('manage-students-btn', 'click', () => studentManager.openRoster());
  safeAdd('duplicate-class-btn', 'click', () => copyManager.openModal());
  safeAdd('delete-class-btn', 'click', profileManager.deleteClass);
  safeAdd('view-defaulters-btn', 'click', defaulterManager.openDefaulterList);
  safeAdd('cold-call-btn', 'click', () => coldCallManager.openModal());

  // --- ADDED THIS LINE ---
  safeAdd('view-leaderboard-btn', 'click', () => leaderboardManager.open());
  // -----------------------

  // 4. Form Submits
  safeAdd('create-class-form', 'submit', (e) => { e.preventDefault(); classManager.startCreateClassStep2(); });
  safeAdd('add-students-form', 'submit', (e) => { e.preventDefault(); classManager.finishCreateClass(); });
  safeAdd('take-attendance-form', 'submit', (e) => { e.preventDefault(); attendance.saveAttendance(); });
  safeAdd('duplicate-class-form', 'submit', (e) => { e.preventDefault(); copyManager.submitCopy(); });

  // 5. Edit Profile (Faculty)
  safeAdd('edit-profile-btn', 'click', profileManager.openModal);
  safeAdd('cancel-edit-profile', 'click', profileManager.closeModal);
  safeAdd('edit-profile-form', 'submit', (e) => { e.preventDefault(); profileManager.saveProfile(); });

  // 6. Edit Student
  safeAdd('cancel-edit-student', 'click', () => studentManager.closeEditForm());
  safeAdd('edit-student-form', 'submit', (e) => { e.preventDefault(); studentManager.saveStudentChange(); });

  // 7. Modals Close Buttons
  safeAdd('cancel-create-class', 'click', modals.hideCreateClassModal);
  safeAdd('cancel-attendance', 'click', modals.hideTakeAttendanceModal);
  safeAdd('back-to-details', 'click', () => { modals.hideAddStudentsModal(); modals.showCreateClassModal(); });

  safeAdd('cancel-duplicate', 'click', copyManager.closeModal);
  safeAdd('close-metrics-btn', 'click', () => { document.getElementById('metrics-modal').classList.add('hidden'); });
  safeAdd('close-roster-btn', 'click', () => { document.getElementById('manage-students-modal').classList.add('hidden'); });
  safeAdd('spin-wheel-btn', 'click', () => coldCallManager.spin());
  safeAdd('btn-send-warnings', 'click', defaulterManager.sendWarnings);
  safeAdd('confirm-download-btn', 'click', reportManager.download);

  // 8. Roster Search
  const searchInput = document.getElementById('roster-search');
  if (searchInput) searchInput.addEventListener('input', (e) => studentManager.filterRoster(e.target.value));

  // Global Esc Key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.form-modal').forEach(m => {
        m.classList.add('hidden');
        m.classList.remove('flex');
      });
    }
  });
};

const profileManager = {
  openModal() {
    // Pre-fill values from the display text
    document.getElementById('edit-name').value = document.getElementById('disp-name').textContent;
    document.getElementById('edit-college_name').value = document.getElementById('disp-college_name').textContent;
    document.getElementById('edit-desig').value = document.getElementById('disp-desig').textContent;
    document.getElementById('edit-dept').value = document.getElementById('disp-dept').textContent;
    document.getElementById('edit-mobile').value = document.getElementById('disp-mobile').textContent;

    // Show Modal
    const modal = document.getElementById('edit-profile-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
  },

  closeModal() {
    const modal = document.getElementById('edit-profile-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  },

  async saveProfile() {
    const formData = new FormData();

    // 1. Append Text Data
    formData.append('name', document.getElementById('edit-name').value);
    formData.append('college_name', document.getElementById('edit-college_name').value);
    formData.append('designation', document.getElementById('edit-desig').value);
    formData.append('department', document.getElementById('edit-dept').value);
    formData.append('mobile', document.getElementById('edit-mobile').value);

    // 2. Append File (Only if a file is selected)
    const fileInput = document.getElementById('edit-profile-photo');
    if (fileInput.files[0]) {
      formData.append('profile_photo', fileInput.files[0]);
    }

    try {
      const response = await fetch(window.djangoUrls.editProfile, {
        method: 'POST',
        // CRITICAL FIX: Do NOT set Content-Type header for FormData.
        // The browser automatically sets it to multipart/form-data with the correct boundary.
        headers: {
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: formData
      });

      if (response.ok) {
        const data = await response.json(); // Get JSON response to check for photo URL

        // 3. Update Text UI elements immediately
        document.getElementById('disp-name').textContent = formData.get('name');
        document.getElementById('disp-college_name').textContent = formData.get('college_name');
        document.getElementById('disp-desig').textContent = formData.get('designation');
        document.getElementById('disp-dept').textContent = formData.get('department');
        document.getElementById('disp-mobile').textContent = formData.get('mobile');

        // 4. Update Profile Photo UI (if server sent back a URL)
        if (data.photo_url) {
          const img = document.getElementById('menu-profile-photo');
          const initialsDiv = document.getElementById('menu-profile-initials');

          if (img) {
            img.src = data.photo_url;
            img.classList.remove('hidden');
          }
          if (initialsDiv) {
            initialsDiv.classList.add('hidden');
          }
        }

        this.closeModal();
        utils.showStatus('Profile updated successfully!');
      } else {
        utils.showStatus('Failed to update profile', true);
      }
    } catch (e) {
      console.error(e);
      utils.showStatus('Network error saving profile', true);
    }
  },

  async deleteClass() {
    const classId = appState.activeClassId;
    if (!classId) return;

    if (!confirm("Are you sure you want to delete this class?\nThis action cannot be undone.")) {
      return;
    }

    const url = window.djangoUrls.deleteClass.replace('0', classId);

    try {
      const response = await fetch(url, {
        method: 'DELETE',
        headers: {
          'X-CSRFToken': getCookie('csrftoken')
        }
      });

      if (response.ok) {
        utils.showStatus('Class deleted.');
        // Remove from local list
        appState.classes = appState.classes.filter(c => c.id !== classId);
        // Go back to home
        navigation.showSection('my-classes');
        // Re-render list
        classManager.renderClasses();
      } else {
        utils.showStatus('Failed to delete class', true);
      }
    } catch (e) {
      console.error(e);
      utils.showStatus('Network error', true);
    }
  }
};

const copyManager = {
  openModal() {
    const classData = appState.currentClassData;
    if (!classData) return;

    // Pre-fill some data? No, usually we want blank for new subject.
    // But we set the source name text.
    document.getElementById('source-class-name').textContent = classData.className;

    // Auto-fill Class Name (User likely wants same class, different subject)
    document.getElementById('dup-class-name').value = classData.className;

    const modal = document.getElementById('duplicate-class-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
  },

  closeModal() {
    const modal = document.getElementById('duplicate-class-modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    document.getElementById('duplicate-class-form').reset();
  },

  async submitCopy() {
    const payload = {
      source_class_id: appState.activeClassId,
      className: document.getElementById('dup-class-name').value,
      subjectName: document.getElementById('dup-subject-name').value,
      subjectCode: document.getElementById('dup-subject-code').value,
      totalHours: document.getElementById('dup-total-hours').value
    };

    utils.showStatus('Duplicating class and roster...');

    try {
      const response = await fetch(window.djangoUrls.copyClass, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        const result = await response.json();
        this.closeModal();
        utils.showStatus('Class duplicated successfully!');

        // Refresh list and go to My Classes to see the new one
        await classManager.fetchClassesFromDB();
        navigation.showSection('my-classes');
      } else {
        utils.showStatus('Failed to duplicate class', true);
      }
    } catch (e) {
      console.error(e);
      utils.showStatus('Network error', true);
    }
  }
};

const defaulterManager = {
  async openDefaulterList() {
    const classId = appState.activeClassId;
    if (!classId) return;

    utils.showStatus('Scanning for defaulters...');
    const url = window.djangoUrls.getDefaulters.replace('0', classId);

    try {
      const response = await fetch(url);
      const data = await response.json();

      if (response.ok) {
        // 1. Set Title
        document.getElementById('defaulter-class-name').textContent = data.className;

        // 2. Render Table
        const tbody = document.getElementById('defaulters-table-body');
        const emptyMsg = document.getElementById('no-defaulters-msg');
        tbody.innerHTML = '';

        if (data.defaulters.length === 0) {
          emptyMsg.classList.remove('hidden');
        } else {
          emptyMsg.classList.add('hidden');

          data.defaulters.forEach(student => {
            const tr = document.createElement('tr');
            tr.className = "hover:bg-slate-700/30 transition";

            // Critical (Red) vs Warning (Orange) styling
            const isCritical = student.severity === 'Critical';
            const badgeColor = isCritical ? 'bg-red-900/50 text-red-400 border-red-800' : 'bg-amber-900/50 text-amber-400 border-amber-800';
            tr.dataset.email = student.email || "";
            tr.dataset.name = student.name;
            tr.dataset.percentage = student.percentage;

            tr.innerHTML = `
                <td class="p-3 font-mono text-slate-300">${student.regNo}</td>
                <td class="p-3 font-medium text-white">
                    ${student.name}
                    ${!student.email ? '<span class="text-xs text-red-500 block">(No Email)</span>' : ''}
                </td>
                <td class="p-3 text-center text-slate-400">${student.present} / ${student.total}</td>
                <td class="p-3 text-center font-bold ${isCritical ? 'text-red-500' : 'text-amber-500'}">${student.percentage}%</td>
                <td class="p-3 text-center">
                    <span class="px-2 py-1 rounded text-xs border ${badgeColor}">${student.severity}</span>
                </td>
                `;
            tbody.appendChild(tr);
          });
        }

        // 3. Show Modal
        const modal = document.getElementById('defaulters-modal');
        modal.classList.remove('hidden');
        modal.classList.add('flex');
      } else {
        utils.showStatus('Error fetching list', true);
      }
    } catch (e) {
      console.error(e);
      utils.showStatus('Network error', true);
    }
  },
  async sendWarnings() {
    if (!confirm("Send email warnings to all displayed students?")) return;

    // Scrape data from the table we just rendered
    const rows = document.querySelectorAll('#defaulters-table-body tr');
    const students = [];
    const subject = appState.currentClassData.subjectName;

    rows.forEach(row => {
      const email = row.dataset.email;
      const name = row.dataset.name;
      const percentage = row.dataset.percentage;
      // In a real app, you'd store email in a data-attribute on the row
      // For now, let's assume we fetch it or it's stored in appState
      // To make this robust, update the 'get_defaulters_list' API to return email
      if (email && email.trim() !== "") {
        students.push({
          name: name,
          email: email,
          subject: subject,
          percentage: percentage
        });
      }
    });

    if (students.length === 0) {
      utils.showStatus("No students have emails registered.", true);
      return;
    }

    utils.showStatus('Sending emails to ${students.length} students...');
    // Fetch call to sendWarnings API...
    try {
      const response = await fetch(window.djangoUrls.sendWarnings, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ students: students })
      });

      const res = await response.json();
      if (response.ok) {
        utils.showStatus(res.message);
      } else {
        utils.showStatus("Failed to send emails", true);
      }
    } catch (e) {
      console.error(e);
    }
  }
};

const coldCallManager = {
  isSpinning: false,

  openModal() {
    const classData = appState.currentClassData;
    if (!classData || classData.students.length === 0) {
      utils.showStatus('No students in class!', true);
      return;
    }

    const modal = document.getElementById('cold-call-modal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    // Reset Text
    document.getElementById('cold-call-display').textContent = "Ready?";
    document.getElementById('cold-call-display').className = "text-3xl md:text-4xl font-bold text-slate-500 h-12 flex items-center justify-center";
    document.getElementById('cold-call-reg').classList.add('opacity-0');

    // Auto spin on open? Optional. Let's wait for click.
  },

  spin() {
    if (this.isSpinning) return;
    const students = appState.currentClassData.students;

    this.isSpinning = true;
    const display = document.getElementById('cold-call-display');
    const regDisplay = document.getElementById('cold-call-reg');
    const btn = document.getElementById('spin-wheel-btn');

    // UI State
    btn.disabled = true;
    btn.classList.add('opacity-50');
    regDisplay.classList.add('opacity-0');
    display.className = "text-3xl md:text-4xl font-bold text-white h-12 flex items-center justify-center";

    let iterations = 0;
    const maxIterations = 20; // How many names to flash
    const speed = 100; // ms

    const interval = setInterval(() => {
      // Pick random student
      const randomStudent = students[Math.floor(Math.random() * students.length)];
      display.textContent = randomStudent.name;

      iterations++;
      if (iterations >= maxIterations) {
        clearInterval(interval);
        this.finalizeSpin(randomStudent);
      }
    }, speed);
  },

  finalizeSpin(winner) {
    const display = document.getElementById('cold-call-display');
    const regDisplay = document.getElementById('cold-call-reg');
    const btn = document.getElementById('spin-wheel-btn');

    // Winner Effect
    display.textContent = winner.name;
    display.className = "text-3xl md:text-4xl font-bold text-pink-400 h-12 flex items-center justify-center animate-bounce";

    regDisplay.textContent = winner.regNo;
    regDisplay.classList.remove('opacity-0');

    // Reset State
    this.isSpinning = false;
    btn.disabled = false;
    btn.classList.remove('opacity-50');
  }
};

const leaderboardManager = {
  async open() {
    const classId = appState.activeClassId;
    utils.showStatus('Calculating ranks...');

    try {
      const response = await fetch(window.djangoUrls.leaderboard.replace('0', classId));
      const data = await response.json();

      const container = document.getElementById('leaderboard-list');
      container.innerHTML = '';

      data.leaderboard.forEach((student, index) => {
        let badge = '';
        let border = 'border-slate-700';
        let text = 'text-white';

        if (index === 0) { badge = '🥇'; border = 'border-yellow-500'; text = 'text-yellow-400'; }
        else if (index === 1) { badge = '🥈'; border = 'border-slate-300'; text = 'text-slate-300'; }
        else if (index === 2) { badge = '🥉'; border = 'border-orange-700'; text = 'text-orange-400'; }
        else { badge = `#${index + 1}`; }

        container.innerHTML += `
                    <div class="flex items-center justify-between p-3 bg-slate-900 rounded-lg border ${border} shadow-md transform hover:scale-105 transition">
                        <div class="flex items-center space-x-3">
                            <span class="text-2xl">${badge}</span>
                            <div>
                                <p class="font-bold ${text}">${student.name}</p>
                                <p class="text-xs text-slate-500 font-mono">${student.regNo}</p>
                            </div>
                        </div>
                        <span class="font-bold text-teal-400">${student.percentage}%</span>
                    </div>
                `;
      });

      document.getElementById('leaderboard-modal').classList.remove('hidden');
      document.getElementById('leaderboard-modal').classList.add('flex');
    } catch (e) { console.error(e); }
  }
};

const reportManager = {
  openModal() {
    document.getElementById('download-report-modal').classList.remove('hidden');
    document.getElementById('download-report-modal').classList.add('flex');

    // Listener for radio buttons to show/hide dates
    document.querySelectorAll('input[name="report-type"]').forEach(r => {
      r.addEventListener('change', (e) => {
        const customDiv = document.getElementById('custom-date-inputs');
        if (e.target.value === 'custom') customDiv.classList.remove('hidden');
        else customDiv.classList.add('hidden');
      });
    });
  },

  download() {
    const type = document.querySelector('input[name="report-type"]:checked').value;
    let url = window.djangoUrls.exportCsv.replace('0', appState.activeClassId);

    if (type === 'custom') {
      const start = document.getElementById('report-start').value;
      const end = document.getElementById('report-end').value;
      if (!start || !end) { utils.showStatus("Select dates", true); return; }
      url += `?filter=custom&start=${start}&end=${end}`;
    } else {
      url += `?filter=${type}`;
    }

    window.location.href = url;
    document.getElementById('download-report-modal').classList.add('hidden');
  }
};
// ==========================================
//  NOTIFICATION & INVITE LOGIC
// ==========================================

const requestManager = {
  showModal(req) {
    let modal = document.getElementById('invite-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'invite-modal';
      modal.className = "fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-[60] animate-fade-in";
      document.body.appendChild(modal);
    }

    // Determine Icon and Colors based on Type
    const isJoin = req.type === 'join';
    const icon = isJoin ? 'building-2' : 'book-open';
    const colorClass = isJoin ? 'text-teal-400 border-teal-500' : 'text-amber-400 border-amber-500';
    const btnColor = isJoin ? 'bg-teal-600 hover:bg-teal-500' : 'bg-amber-600 hover:bg-amber-500';

    modal.innerHTML = `
            <div class="bg-slate-900 border-2 ${isJoin ? 'border-teal-500' : 'border-amber-500'} rounded-2xl p-8 max-w-md w-full shadow-2xl relative overflow-hidden">
                <div class="absolute top-0 right-0 w-24 h-24 ${isJoin ? 'bg-teal-500/10' : 'bg-amber-500/10'} rounded-bl-full -mr-4 -mt-4"></div>
                
                <div class="text-center mb-6 relative z-10">
                    <div class="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4 border ${colorClass}">
                        <i data-lucide="${icon}" class="w-8 h-8"></i>
                    </div>
                    <h2 class="text-2xl font-bold text-white">${req.title}</h2>
                    <p class="text-slate-300 mt-2 text-sm leading-relaxed">${req.subtitle}</p>
                    <div class="mt-3 inline-block px-3 py-1 rounded bg-slate-800 border border-slate-700 text-xs font-mono text-slate-400">
                        ${req.meta}
                    </div>
                </div>

                <div class="grid grid-cols-2 gap-4">
                    <button onclick="requestManager.respond(${req.request_id}, '${req.type}', 'Reject')" class="py-3 bg-slate-800 hover:bg-red-900/50 text-slate-300 hover:text-red-400 rounded-xl font-bold transition border border-transparent hover:border-red-500/50">
                        Reject
                    </button>
                    <button onclick="requestManager.respond(${req.request_id}, '${req.type}', 'Accept')" class="py-3 ${btnColor} text-white rounded-xl font-bold shadow-lg transition transform active:scale-95">
                        Accept
                    </button>
                </div>
            </div>
        `;
    modal.classList.remove('hidden');
    if (window.lucide) lucide.createIcons();
  },

  async respond(id, type, action) {
    if (!confirm(`Are you sure you want to ${action}?`)) return;

    try {
      const res = await fetch(window.djangoUrls.respondRequest, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify({
          request_id: id,
          type: type, // <--- CRITICAL: Sending type so backend knows what to accept
          action: action
        })
      });

      const data = await res.json();

      const modal = document.getElementById('invite-modal');
      if (modal) modal.remove();

      alert(data.message);

      if (action === 'Accept') {
        location.reload(); // Reload to see new class or college info
      } else {
        notifMgr.fetchRequests(); // Just refresh list
      }
    } catch (e) { console.error(e); alert("Network Error"); }
  }
};

const notifMgr = {
  toggle() {
    const dd = document.getElementById('notif-dropdown');
    if (dd.classList.contains('hidden')) {
      dd.classList.remove('hidden');
      this.fetchRequests();
    } else {
      dd.classList.add('hidden');
    }
  },

  async fetchRequests() {
    try {
      const url = window.djangoUrls.getRequests;
      if (!url) return;

      const res = await fetch(url);
      const data = await res.json();
      this.render(data.requests || []);
    } catch (e) { console.error("Notif Error", e); }
  },

  render(requests) {
    const list = document.getElementById('notif-list');
    const badge = document.getElementById('notif-badge');
    const mobBadge = document.getElementById('mobile-notif-badge');

    if (!list) return;
    list.innerHTML = '';

    if (requests.length > 0) {
      if (badge) badge.classList.remove('hidden');
      if (mobBadge) mobBadge.classList.remove('hidden');

      requests.forEach(req => {
        const item = document.createElement('div');
        item.className = "p-3 hover:bg-slate-700/50 rounded-lg cursor-pointer transition border-b border-slate-700/50 last:border-0";
        item.onclick = () => requestManager.showModal(req);

        // Dynamic Icon
        const icon = req.type === 'join' ? 'user-plus' : 'book-open';
        const color = req.type === 'join' ? 'text-teal-400' : 'text-amber-400';
        const bg = req.type === 'join' ? 'bg-teal-900/30' : 'bg-amber-900/30';

        item.innerHTML = `
                    <div class="flex items-start gap-3">
                        <div class="p-2 ${bg} rounded-full ${color} mt-1"><i data-lucide="${icon}" class="w-4 h-4"></i></div>
                        <div>
                            <p class="text-sm text-white font-bold">${req.title}</p>
                            <p class="text-xs text-slate-400 mt-0.5 line-clamp-2">${req.subtitle}</p>
                            <p class="text-[10px] ${color} font-bold mt-2 uppercase tracking-wide">Review Request</p>
                        </div>
                    </div>
                `;
        list.appendChild(item);
      });
      if (window.lucide) lucide.createIcons();
    } else {
      if (badge) badge.classList.add('hidden');
      if (mobBadge) mobBadge.classList.add('hidden');
      list.innerHTML = `<p class="text-xs text-slate-500 text-center py-4">No pending requests</p>`;
    }
  },
  async markRead(id, btn) {
    btn.closest('div.group').remove();
    // Fetch call to /api/mark-notif-read/ ...
  },
};

// CRITICAL: Expose to window so HTML onclick works
window.requestManager = requestManager;
window.notifMgr = notifMgr;

// Start checking
document.addEventListener('DOMContentLoaded', () => {
  notifMgr.fetchRequests();
});

// Auto-check on load
document.addEventListener('DOMContentLoaded', () => {
  if (window.notifMgr) {
    notifMgr.fetchRequests();
  }
});
// Initialize Application
const initApp = () => {
  // Only call fetch. The fetch function will call renderClasses when it's done.
  classManager.fetchClassesFromDB();

  setupEventListeners();

  const today = utils.formatDate(new Date());
  elements.attendanceDate.value = today;
  elements.attendanceDate.min = utils.formatDate(new Date(Date.now() - 3 * 24 * 60 * 60 * 1000));
  elements.attendanceDate.max = today;

  setTimeout(() => {
    utils.showStatus('Welcome to Present Sir!!! Dashboard');
  }, 1000);
};
// Start the application when DOM is loaded
document.addEventListener('DOMContentLoaded', initApp);

// Make functions available globally for inline handlers
window.attendance = attendance;