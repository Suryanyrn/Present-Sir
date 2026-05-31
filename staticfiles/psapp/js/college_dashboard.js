// ==========================================
//  CSRF TOKEN UTILITIES
// ==========================================
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

// ==========================================
//  GLOBAL STATE
// ==========================================
const state = {
    departments: [],
    faculty: [],
    currentDeptId: null,
    currentClassId: null,
    currentRoster: [],
    searchedFacultyId: null,
    tempClassData: {}
};
// ==========================================
//  1. UI 
// ==========================================
const ui = {
    init() {
        this.switchTab('departments');
        this.populateYearDropdown();
        api.fetchData();
        if (window.adminNotif) adminNotif.fetch();
    },

    populateYearDropdown() {
        const select = document.getElementById('inp-dept-year');
        if (!select) return;
        const currentYear = new Date().getFullYear();
        let html = '';
        for (let year = currentYear; year >= 1900; year--) {
            html += `<option value="${year}">${year}</option>`;
        }
        select.innerHTML = html;
    },

    switchTab(tabName) {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active', 'text-teal-400', 'border-teal-400');
            btn.classList.add('text-slate-400', 'border-transparent');
        });

        ['view-departments', 'view-classes', 'view-faculty', 'view-students', 'view-profile'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });

        const navBtn = document.getElementById(`nav-${tabName}`);
        const viewSection = document.getElementById(`view-${tabName}`);

        if (navBtn && viewSection) {
            navBtn.classList.add('active', 'text-teal-400', 'border-teal-400');
            navBtn.classList.remove('text-slate-400', 'border-transparent');
            viewSection.classList.remove('hidden');
        }

        if (tabName === 'classes') this.renderClassesAnalytics();
        if (tabName === 'faculty') this.renderFacultyDirectory();
        if (tabName === 'students') studentMgr.init();
        document.querySelectorAll('.mobile-tab-btn').forEach(btn => {
            const iconSpan = btn.querySelector('span'); // The text label
            const iconContainer = btn.querySelector('.icon-container'); // The icon box

            if (btn.dataset.target === tabName) {
                // Active State
                btn.classList.add('active', 'text-teal-400');
                btn.classList.remove('text-slate-500');
                iconContainer.classList.add('bg-teal-500/10'); // Subtle glow background
            } else {
                // Inactive State
                btn.classList.remove('active', 'text-teal-400');
                btn.classList.add('text-slate-500');
                iconContainer.classList.remove('bg-teal-500/10');
            }
        });
    },

    renderDepartments(depts) {
        const container = document.getElementById('dept-grid');
        if (!container) return;
        container.innerHTML = '';

        if (!depts || depts.length === 0) {
            container.innerHTML = `<div class="col-span-full py-10 text-center border-2 border-dashed border-slate-800 rounded-2xl text-slate-500">No departments found. Add one to get started.</div>`;
            return;
        }

        depts.forEach(d => {
            const classCount = d.classCount || 0;
            const facultyCount = d.facultyCount || 0;
            const year = d.year || 'N/A';

            const card = document.createElement('div');
            card.className = "bg-slate-800 rounded-2xl p-6 border border-slate-700 shadow-xl hover:border-teal-500/30 transition group relative overflow-hidden";
            card.innerHTML = `
                <div class="absolute top-0 right-0 w-32 h-32 bg-teal-500/5 rounded-bl-full -mr-10 -mt-10 transition group-hover:bg-teal-500/10"></div>
                <div class="flex justify-between items-start relative z-10">
                    <div>
                        <h3 class="text-2xl font-bold text-white">${d.name}</h3>
                        <p class="text-sm text-slate-400 mt-1 flex items-center gap-1"><i data-lucide="calendar" class="w-3 h-3"></i> Est. ${year}</p>
                    </div>
                    <div class="w-10 h-10 bg-slate-900 rounded-lg flex items-center justify-center text-teal-400 border border-slate-700"><i data-lucide="layers" class="w-5 h-5"></i></div>
                </div>
                <div class="grid grid-cols-2 gap-4 mt-6 mb-6">
                    <div class="bg-slate-900/50 p-3 rounded-xl border border-slate-700/50"><span class="text-2xl font-bold text-white block">${classCount}</span><span class="text-[10px] uppercase text-slate-500 font-bold tracking-wider">Classes</span></div>
                    <div class="bg-slate-900/50 p-3 rounded-xl border border-slate-700/50"><span class="text-2xl font-bold text-white block">${facultyCount}</span><span class="text-[10px] uppercase text-slate-500 font-bold tracking-wider">Faculty</span></div>
                </div>
                <button onclick="window.modals.openManageDept(${d.id})" class="w-full py-3 bg-slate-700 hover:bg-teal-600 text-white rounded-xl font-semibold text-sm transition flex items-center justify-center gap-2"><i data-lucide="settings-2" class="w-4 h-4"></i> Manage Resources</button>
            `;
            container.appendChild(card);
        });

        // Trigger Profile Render too
        this.renderProfileDepartments(depts);

        if (window.lucide) lucide.createIcons();
    },

    renderProfileDepartments(depts) {
        const tbody = document.getElementById('profile-dept-list');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (!depts || depts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="p-4 text-center text-slate-500">No departments to manage.</td></tr>';
            return;
        }

        depts.forEach(d => {
            tbody.innerHTML += `
                <tr class="hover:bg-red-900/10 transition">
                    <td class="p-4 font-medium text-white">${d.name}</td>
                    <td class="p-4 text-center text-slate-400">${d.year}</td>
                    <td class="p-4 text-right">
                        <button onclick="dangerMgr.confirmDelete('dept', ${d.id})" class="text-xs bg-red-900/30 text-red-400 border border-red-900/50 hover:bg-red-600 hover:text-white px-3 py-1.5 rounded transition font-bold flex items-center gap-1 ml-auto">
                            <i data-lucide="trash-2" class="w-3 h-3"></i> Delete
                        </button>
                    </td>
                </tr>
            `;
        });
    },

    renderClassesAnalytics() {
        const container = document.getElementById('classes-analytics-container');
        if (!container) return;
        container.innerHTML = '';

        if (!state.departments || state.departments.length === 0) {
            container.innerHTML = '<p class="text-slate-500 text-center">No data available.</p>';
            return;
        }

        state.departments.forEach(dept => {
            if (!dept.classes || dept.classes.length === 0) return;
            const section = document.createElement('div');
            section.className = "bg-slate-900/50 border border-slate-800 rounded-2xl p-6 animate-fade-in";
            let html = `<div class="flex items-center gap-3 mb-6"><div class="w-1.5 h-6 bg-teal-500 rounded-full"></div><h3 class="text-xl font-bold text-white">${dept.name}</h3></div><div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">`;

            dept.classes.forEach(cls => {
                html += `
                    <div onclick="api.getClassDetails(${cls.id})" class="bg-slate-800 p-5 rounded-xl border border-slate-700 hover:border-blue-500/50 hover:shadow-lg hover:-translate-y-1 transition cursor-pointer group">
                        <div class="flex justify-between items-start mb-3">
                            <div><h4 class="text-lg font-bold text-white group-hover:text-blue-400 transition">${cls.name}</h4><p class="text-xs text-slate-400 font-mono mt-1">${cls.batch || 'N/A'}</p></div>
                            <span class="bg-blue-500/10 text-blue-400 text-xs px-2 py-1 rounded font-bold">Year ${cls.year}</span>
                        </div>
                        <div class="flex items-center gap-2 text-xs text-slate-500 mt-2"><i data-lucide="users" class="w-3 h-3"></i> View Roster</div>
                    </div>`;
            });
            html += `</div>`;
            section.innerHTML = html;
            container.appendChild(section);
        });
        if (window.lucide) lucide.createIcons();
    },

    renderFacultyDirectory() {
        const container = document.getElementById('faculty-list-container');
        if (!container) return;
        container.innerHTML = '';
        const list = state.faculty || [];

        if (list.length === 0) {
            container.innerHTML = `<div class="flex flex-col items-center justify-center py-20 text-slate-500 border-2 border-dashed border-slate-800 rounded-2xl"><i data-lucide="users" class="w-12 h-12 mb-4 opacity-20"></i><p class="text-lg">No faculty members found.</p></div>`;
            if (window.lucide) lucide.createIcons();
            return;
        }

        const grid = document.createElement('div');
        grid.className = "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6";

        list.forEach(fac => {
            const initials = fac.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
            const photoHtml = fac.photo ? `<img src="${fac.photo}" class="w-full h-full object-cover">` : `<div class="w-full h-full bg-slate-700 flex items-center justify-center text-2xl font-bold text-slate-500">${initials}</div>`;

            // --- ID DISPLAY LOGIC ---
            const facIdDisplay = fac.reg_id ? `<span class="text-[10px] font-mono text-slate-500 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-700 select-all">${fac.reg_id}</span>` : '';

            const card = document.createElement('div');
            card.onclick = () => facultyMgr.openDetails(fac.id);
            card.className = "group bg-slate-800 rounded-2xl border border-slate-700 overflow-hidden hover:border-teal-500/50 transition shadow-lg relative cursor-pointer";
            card.innerHTML = `
                <div class="p-6 flex items-start gap-4">
                    <div class="w-16 h-16 rounded-full overflow-hidden border-2 border-slate-600 shrink-0 shadow-md">${photoHtml}</div>
                    <div class="flex-1 min-w-0">
                        <h3 class="text-lg font-bold text-white truncate">${fac.name}</h3>
                        <p class="text-teal-400 text-sm font-medium truncate">${fac.designation}</p>
                        
                        <div class="flex flex-wrap items-center gap-2 mt-2">
                            <span class="bg-slate-900 text-slate-400 text-[10px] px-2 py-0.5 rounded border border-slate-700 uppercase tracking-wide">${fac.department}</span>
                            ${facIdDisplay}
                        </div>
                    </div>
                </div>
                <div class="bg-slate-900/50 px-6 py-3 border-t border-slate-700 flex justify-between items-start text-xs text-slate-400">
                    <div class="flex flex-col gap-1.5">
                        <span class="flex items-center"><i data-lucide="mail" class="w-3 h-3 mr-2 text-slate-500"></i>${fac.email}</span>
                        <span class="flex items-center"><i data-lucide="phone" class="w-3 h-3 mr-2 text-slate-500"></i>${fac.mobile}</span>
                    </div>
                </div>
            `;
            grid.appendChild(card);
        });
        container.appendChild(grid);
        if (window.lucide) lucide.createIcons();
    },

    updateProfileStats(stats) {
        const d = document.getElementById('stat-total-depts');
        const f = document.getElementById('stat-total-faculty');
        if (d) d.textContent = stats.total_depts || 0;
        if (f) f.textContent = stats.total_faculty || 0;
    },
    calcBatchYear() {
        const startInput = document.getElementById('cls-batch-start');
        const endInput = document.getElementById('cls-batch-end');
        const display = document.getElementById('cls-current-year-display');
        const hiddenVal = document.getElementById('cls-current-year');
        const warningEl = document.getElementById('batch-warning');

        // 1. Get Values
        const startYear = parseInt(startInput.value);
        const endYear = parseInt(endInput.value);

        // Get Current Academic Year (From hidden input or System Date)
        // Assuming Academic Year starts in June/August.
        // If hidden input value is "2025" (representing 2025-2026)
        const academicStartYear = parseInt(document.getElementById('sys-academic-year').value) || new Date().getFullYear();

        // Reset UI
        display.value = "";
        hiddenVal.value = "";
        warningEl.classList.add('hidden');
        display.classList.remove('text-red-400', 'text-teal-400');

        // 2. Validate Basic Numbers
        if (!startYear) return; // Wait for input

        if (endYear && endYear <= startYear) {
            warningEl.textContent = "End year must be greater than Start year.";
            warningEl.classList.remove('hidden');
            return;
        }

        // 3. Auto-Calculate End Year (Optional UX Helper)
        // If user types 2023, we can guess 2027 (4 years is standard B.Tech)
        // You can enable this if you want:
        // if (!endYear && startYear > 2000) { document.getElementById('cls-batch-end').value = startYear + 4; }

        // 4. Calculate Current Year
        // Logic: (2025 - 2023) + 1 = 3rd Year
        const diff = (academicStartYear - startYear) + 1;

        // 5. Roman Numeral Map
        const roman = ["", "I", "II", "III", "IV", "V", "VI"];

        if (diff > 0 && diff <= 6) {
            // Valid Year
            display.value = `${roman[diff]} Year`;
            hiddenVal.value = diff; // Store integer 3
            display.classList.add('text-teal-400');

            // Validation: Is the batch over?
            if (endYear && startYear + diff > endYear) {
                display.value = "Graduated / Alumni";
                display.classList.remove('text-teal-400');
                display.classList.add('text-slate-400');
                hiddenVal.value = "Alumni";
            }
        } else if (diff > 6) {
            display.value = "Alumni";
            hiddenVal.value = "Alumni";
            display.classList.add('text-slate-400');
        } else {
            // Future Batch
            display.value = "Future Batch";
            display.classList.add('text-slate-400');
            warningEl.textContent = "Batch starts in the future.";
            warningEl.classList.remove('hidden');
        }
    },
};

// ==========================================
//  2. RESOURCE MANAGER (Dept, Faculty, Class Creation)
// ==========================================
const resourceMgr = {
    open(deptId) {
        const dept = state.departments.find(d => d.id === deptId);
        if (!dept) return;
        state.currentDeptId = dept.id;
        document.getElementById('manage-dept-title').textContent = dept.name;
        document.getElementById('manage-dept-year').textContent = dept.year || 'N/A';
        const modal = document.getElementById('modal-manage-dept');
        modal.classList.remove('hidden'); modal.classList.add('flex');
        this.showHome();
    },

    hideAllViews() {
        ['res-view-home', 'res-view-class', 'res-view-students', 'res-view-faculty', 'res-view-course', 'res-view-subjects-list'].forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });
    },

    toggleBackButton(show) {
        const btn = document.getElementById('btn-back-home');
        if (btn) show ? btn.classList.remove('hidden') : btn.classList.add('hidden');
    },

    showHome() {
        this.hideAllViews();
        document.getElementById('res-view-home').classList.remove('hidden');
        this.toggleBackButton(false);
    },

    showAddClass() {
        this.hideAllViews();
        document.getElementById('res-view-class').classList.remove('hidden');
        this.toggleBackButton(true);
        document.getElementById('cls-name').value = '';
        document.getElementById('cls-batch-name').value = '';
        document.getElementById('cls-total-stu').value = '';
    },

    showAddFaculty() {
        this.hideAllViews();
        document.getElementById('res-view-faculty').classList.remove('hidden');
        this.toggleBackButton(true);
        document.getElementById('fac-search-input').value = '';
        document.getElementById('fac-result-card').classList.add('hidden');
    },

    // --- Student Entry Logic (Create Class Step 2) ---
    goToStudentEntry() {
        const name = document.getElementById('cls-name').value.trim();
        const start = document.getElementById('cls-batch-start').value;
        const end = document.getElementById('cls-batch-end').value;
        const batch = `${start}-${end}`;
        const count = parseInt(document.getElementById('cls-total-stu').value);
        const batchName = document.getElementById('cls-batch-name').value.trim();
        const currYear = document.getElementById('cls-current-year').value;

        if (!name || !count || count < 1) return alert("Please fill class name and valid student count.");
        if (!currYear) return alert("Invalid Batch Years. Check calculation.");
        state.tempClassData = { name, batch, count, currYear, batchName };

        const container = document.getElementById('student-rows-container');
        container.innerHTML = '';

        for (let i = 1; i <= count; i++) {
            container.innerHTML += `
                <div class="student-row grid grid-cols-12 gap-2 items-center bg-slate-900/80 p-2 rounded-lg border border-slate-700/50 mb-2">
                    <span class="col-span-1 text-slate-500 text-xs font-mono text-center font-bold">#${i}</span>
                    <div class="col-span-3"><input type="text" class="stu-reg w-full bg-slate-800 border border-slate-600 rounded text-xs text-white p-2" placeholder="Reg No *"></div>
                    <div class="col-span-4"><input type="text" class="stu-name w-full bg-slate-800 border border-slate-600 rounded text-xs text-white p-2" placeholder="Student Name *"></div>
                    <div class="col-span-4"><input type="email" class="stu-email w-full bg-slate-800 border border-slate-600 rounded text-xs text-white p-2" placeholder="Email (Optional)"></div>
                </div>`;
        }
        document.getElementById('student-entry-count').textContent = count;
        this.hideAllViews();
        document.getElementById('res-view-students').classList.remove('hidden');
        this.toggleBackButton(true);
    },

    // --- Submit Class ---
    async submitClass() {
        const studentRows = document.querySelectorAll('.student-row');
        const students = [];
        let error = false;

        studentRows.forEach(row => {
            const reg = row.querySelector('.stu-reg').value.trim();
            const name = row.querySelector('.stu-name').value.trim();
            const email = row.querySelector('.stu-email').value.trim();
            if (reg && name) {
                students.push({ regNo: reg, name: name, email: email });
            } else {
                error = true;
                row.classList.add('border-red-500');
            }
        });

        if (students.length === 0) return alert("Fill at least one student.");
        if (error && !confirm("Some rows are empty. Continue?")) return;

        const payload = {
            dept_id: state.currentDeptId,
            name: state.tempClassData.name,
            acad_year: state.tempClassData.batch,
            currentYear: state.tempClassData.currYear,
            batch_name: state.tempClassData.batchName,
            students: students
        };

        try {
            const res = await fetch(window.djangoUrls.addClass, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCookie('csrftoken'), 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                alert("Class Created Successfully!");
                modals.close('modal-manage-dept');
                api.fetchData();
            } else {
                const d = await res.json();
                alert(d.error || "Failed");
            }
        } catch (e) { alert("Network Error"); }
    },

    // --- Faculty Invite Logic ---
    foundFacultyId: null,
    async searchFaculty() {
        const input = document.getElementById('fac-search-input');
        const regId = input.value.trim();
        const card = document.getElementById('fac-result-card');

        if (!regId) return alert("Please enter a Faculty ID.");

        card.classList.add('hidden');
        this.foundFacultyId = null;

        try {
            const res = await fetch(`${window.djangoUrls.searchFacultyId}?reg_id=${encodeURIComponent(regId)}`);
            const data = await res.json();

            if (data.found) {
                this.foundFacultyId = data.id;
                document.getElementById('fac-res-name').textContent = data.name;
                document.getElementById('fac-res-email').textContent = data.email;
                document.getElementById('fac-res-initials').textContent = data.name.substring(0, 2).toUpperCase();
                card.classList.remove('hidden');
            } else {
                alert("Faculty ID not found in database.");
            }
        } catch (e) { console.error(e); }
    },

    async sendInvite() {
        if (!this.foundFacultyId) return alert("Please search for a faculty member first.");
        if (!state.currentDeptId) return alert("Error: Department context missing. Reload page.");

        const btn = document.querySelector('#fac-result-card button');
        btn.disabled = true;
        btn.textContent = "Sending...";

        try {
            const res = await fetch(window.djangoUrls.sendInvite, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify({ faculty_db_id: this.foundFacultyId, dept_id: state.currentDeptId })
            });

            const data = await res.json();
            if (res.ok) {
                alert(data.message);
                document.getElementById('fac-search-input').value = '';
                document.getElementById('fac-result-card').classList.add('hidden');
                this.foundFacultyId = null;
            } else {
                alert("Error: " + data.error);
            }
        } catch (e) { console.error(e); }
        finally { btn.disabled = false; btn.textContent = "Send Join Request"; }
    },

    // --- Subject/Course Management Logic ---
    async showManageSubjects() {
        this.hideAllViews();
        this.toggleBackButton(true);
        document.getElementById('res-view-subjects-list').classList.remove('hidden');

        const tbody = document.getElementById('subject-list-body');
        tbody.innerHTML = '<tr><td colspan="3" class="text-center py-8 text-slate-500">Loading...</td></tr>';

        try {
            // FIX: Using .getCourses here
            const res = await fetch(`${window.djangoUrls.getCourses}?dept_id=${state.currentDeptId}`);
            const data = await res.json();
            tbody.innerHTML = '';
            if (data.courses.length === 0) {
                document.getElementById('no-subjects-msg').classList.remove('hidden');
            } else {
                document.getElementById('no-subjects-msg').classList.add('hidden');
                const grouped = data.courses.reduce((acc, course) => {
                    const key = course.type === 'Elective' ? 'Electives' : `Semester ${course.semester}`;
                    if (!acc[key]) acc[key] = [];
                    acc[key].push(course);
                    return acc;
                }, {});

                // Sort keys: Sem 1, Sem 2 ... Electives
                const sortedKeys = Object.keys(grouped).sort((a, b) => {
                    if (a === 'Electives') return 1;
                    if (b === 'Electives') return -1;
                    return a.localeCompare(b, undefined, { numeric: true });
                });

                sortedKeys.forEach(sem => {
                    // Add Section Header
                    tbody.innerHTML += `
                        <tr class="bg-slate-800 border-b border-slate-700">
                            <td colspan="3" class="py-2 px-4 text-xs font-bold text-teal-400 uppercase tracking-wider">
                                ${sem}
                            </td>
                        </tr>
                    `;
                    // Add Rows
                    grouped[sem].forEach(c => {
                        tbody.innerHTML += `
                            <tr class="group hover:bg-slate-800/50 transition">
                                <td class="py-3 pl-4 font-mono text-slate-300 text-sm border-l-2 border-transparent hover:border-teal-500">${c.code}</td>
                                <td class="py-3 font-medium text-white">
                                    ${c.title}
                                    ${c.type === 'Elective' ? '<span class="text-[10px] bg-purple-900/30 text-purple-400 px-1 rounded ml-2">Elective</span>' : ''}
                                </td>
                                <td class="py-3 text-right pr-4 flex justify-end gap-2 opacity-60 group-hover:opacity-100 transition">
                                    <button onclick="resourceMgr.prepEditCourse(${c.id}, '${c.title}', '${c.code}')" class="p-1.5 bg-blue-900/30 text-blue-400 hover:bg-blue-600 hover:text-white rounded"><i data-lucide="pencil" class="w-4 h-4"></i></button>
                                    <button onclick="resourceMgr.deleteSubject(${c.id})" class="p-1.5 bg-red-900/30 text-red-400 hover:bg-red-600 hover:text-white rounded"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
                                </td>
                            </tr>`;
                    });
                });
                lucide.createIcons();
            }
        } catch (e) { console.error(e); }
    },

    showAddCourse() {
        this.hideAllViews();
        document.getElementById('res-view-course').classList.remove('hidden');
        this.toggleBackButton(true);
        document.getElementById('course-title-in').value = '';
        document.getElementById('course-code-in').value = '';
        const btn = document.getElementById('btn-submit-course');
        btn.textContent = "Add Subject";
        btn.dataset.mode = "new";
        btn.dataset.editId = "";
    },

    prepEditCourse(id, title, code) {
        this.showAddCourse();
        document.getElementById('course-title-in').value = title;
        document.getElementById('course-code-in').value = code;
        const btn = document.getElementById('btn-submit-course');
        btn.textContent = "Update Subject";
        btn.dataset.mode = "edit";
        btn.dataset.editId = id;
    },

    async submitCourse() {
        const title = document.getElementById('course-title-in').value.trim();
        const code = document.getElementById('course-code-in').value.trim();
        const sem = document.getElementById('course-sem-in').value;
        const type = document.getElementById('course-type-in').value;
        if (!title || !code) return alert("Fill all fields");

        const btn = document.getElementById('btn-submit-course');
        const isEdit = (btn.dataset.mode === 'edit');
        const formData = new FormData();
        formData.append('course_title', title);
        formData.append('course_code', code);
        formData.append('semester', sem); // NEW
        formData.append('course_type', type);

        let url = window.djangoUrls.addCourse;
        if (isEdit) {
            url = window.djangoUrls.editCourse;
            formData.append('course_id', btn.dataset.editId);
        } else {
            formData.append('dept_id', state.currentDeptId);
        }

        try {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken() },
                body: formData
            });
            if (res.ok) {
                this.showManageSubjects();
            } else {
                alert("Operation failed.");
            }
        } catch (e) { alert("Network Error"); }
    },

    async deleteSubject(id) {
        if (!confirm("Are you sure?")) return;
        const formData = new FormData();
        formData.append('course_id', id);
        try {
            const res = await fetch(window.djangoUrls.deleteCourse, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken() },
                body: formData
            });
            if (res.ok) this.showManageSubjects();
        } catch (e) { alert("Network Error"); }
    },

    // --- Assign Faculty to Class Logic ---

    populateFacultyDropdown() {
        const container = document.getElementById('assign-faculty-container');
        if (!container) return;

        // 1. Render Search Input + List Container (Empty on open, only show on type)
        container.innerHTML = `
            <input type="text" id="fac-assign-search" onkeyup="resourceMgr.filterFacultyList()" 
                   class="w-full bg-slate-900 border border-slate-600 text-white rounded-lg p-3 outline-none focus:border-teal-500 mb-2" 
                   placeholder="Type to search faculty..." />
            <div id="fac-assign-list" class="max-h-32 overflow-y-auto custom-scroll border border-slate-700 rounded-lg bg-slate-900"></div>
            <input type="hidden" id="assign-faculty-select" /> `;

        // Start empty - only populate on user input
        const listDiv = document.getElementById('fac-assign-list');
        listDiv.innerHTML = '<div class="p-2 text-xs text-slate-400 italic">Type faculty name to search...</div>';
    },
    filterFacultyList() {
        const query = document.getElementById('fac-assign-search').value.toLowerCase().trim();
        const listDiv = document.getElementById('fac-assign-list');

        // If query is empty, show placeholder
        if (!query) {
            listDiv.innerHTML = '<div class="p-2 text-xs text-slate-400 italic">Type faculty name to search...</div>';
            return;
        }

        // Filter and render only when user has typed something
        const filtered = (state.faculty || []).filter(f =>
            f.name.toLowerCase().includes(query) || (f.department && f.department.toLowerCase().includes(query))
        );
        this.renderFacultyListItems(filtered);
    },

    renderFacultyListItems(list) {
        const listDiv = document.getElementById('fac-assign-list');
        listDiv.innerHTML = '';
        if (list.length === 0) {
            listDiv.innerHTML = '<div class="p-2 text-xs text-slate-500">No matches found</div>';
            return;
        }
        list.forEach(f => {
            const item = document.createElement('div');
            item.className = "p-2 hover:bg-teal-900/30 cursor-pointer border-b border-slate-800 last:border-0 text-sm text-slate-300 flex items-start justify-between gap-3";

            const left = document.createElement('div');
            left.innerHTML = `<div class="font-bold text-white text-sm">${f.name.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div><div class="text-xs text-slate-400">${(f.department||'').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>`;

            const right = document.createElement('div');
            right.className = 'text-xs text-slate-400 text-right';
            const email = f.email ? f.email.replace(/</g, '&lt;').replace(/>/g, '&gt;') : '';
            const rid = f.reg_id ? `<div class="text-[10px] text-slate-500 mt-1 font-mono">${String(f.reg_id).replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>` : '';
            right.innerHTML = `${email}${rid}`;

            item.appendChild(left);
            item.appendChild(right);

            item.onclick = () => {
                // Select Logic
                document.getElementById('assign-faculty-select').value = f.id;
                document.getElementById('fac-assign-search').value = f.name; // Show name
                // Highlight selection
                Array.from(listDiv.children).forEach(c => c.classList.remove('bg-teal-600', 'text-white'));
                item.classList.add('bg-teal-600', 'text-white');
            };

            listDiv.appendChild(item);
        });
    },
    openAssignModal(preSelectSubjectCode = null) {
        // ... (Existing checks) ...
        const modal = document.getElementById('modal-assign-course');
        modal.classList.remove('hidden'); modal.classList.add('flex');

        this.populateFacultyDropdown(); // Uses new Searchable Logic

        // Populate Subjects
        const subjSelect = document.getElementById('assign-subject-select');

        // If Reassigning (Code passed), Lock the dropdown
        if (preSelectSubjectCode) {
            subjSelect.disabled = true;
            subjSelect.classList.add('opacity-50', 'cursor-not-allowed');
            // We wait for populate to finish then select it
            this.populateSubjectDropdown(preSelectSubjectCode).then(() => {
                // Force Select
                // Logic handled inside populateSubjectDropdown via 'selected' attribute
            });
        } else {
            subjSelect.disabled = false;
            subjSelect.classList.remove('opacity-50', 'cursor-not-allowed');
            this.populateSubjectDropdown(null);
        }
    },

    async populateSubjectDropdown(preSelectCode) {
        const subjSelect = document.getElementById('assign-subject-select');
        subjSelect.innerHTML = '<option>Loading subjects...</option>';

        // 1. ROBUST ID FETCHING
        let deptId = state.currentClassDeptId;

        // Fallback 1: Check App State
        if (!deptId && state.currentClassId && typeof appState !== 'undefined' && appState.classes) {
            const cls = appState.classes.find(c => c.id == state.currentClassId);
            if (cls) deptId = cls.dept_id;
        }

        // Fallback 2: Check Main Dept View
        if (!deptId) deptId = state.currentDeptId;

        if (!deptId) {
            subjSelect.innerHTML = '<option disabled>Error: Department Context Lost. Reload Page.</option>';
            return;
        }

        try {
            // FIX: Using .getCourses to match your HTML definition
            const res = await fetch(`${window.djangoUrls.getCourses}?dept_id=${deptId}`);
            const data = await res.json();

            subjSelect.innerHTML = '<option value="">Select Subject</option>';

            if (data.courses && data.courses.length > 0) {
                data.courses.forEach(c => {
                    const isSelected = (preSelectCode && c.code === preSelectCode) ? 'selected' : '';
                    subjSelect.innerHTML += `<option value="${c.id}" ${isSelected}>${c.title} (${c.code})</option>`;
                });
            } else {
                subjSelect.innerHTML += '<option disabled>No subjects found for this department</option>';
            }
        } catch (e) {
            console.error(e);
            subjSelect.innerHTML = '<option disabled>Error loading data</option>';
        }
    },

    async submitAssignment() {
        const classId = state.currentClassId;
        const subId = document.getElementById('assign-subject-select').value;
        const facId = document.getElementById('assign-faculty-select').value;
        const hours = document.getElementById('assign-total-hours').value;

        const hoursNum = parseInt(hours, 10);
        if (!subId || !facId || !hours || isNaN(hoursNum) || hoursNum <= 0) return alert("Please fill all fields with valid values");
        const btn = document.getElementById('btn-assign-confirm');
        const ogText = btn ? btn.innerText : 'Assigning...';
        if (btn) { btn.innerText = "Assigning..."; btn.disabled = true; }

        try {
            const res = await fetch(window.djangoUrls.assignCourse, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify({ class_id: classId, subject_id: subId, faculty_id: facId, total_hours: hours })
            });
            const data = await res.json();
            if (res.ok) {
                alert(data.message);
                document.getElementById('modal-assign-course').classList.add('hidden');
                // Refresh assigned list if classMgr is active
                if (typeof classMgr !== 'undefined') classMgr.showAssigned();
            } else {
                alert("Error: " + data.error);
            }
        } catch (e) { alert("Network Error"); }
        finally { if (btn) { btn.innerText = ogText; btn.disabled = false; } }
    }
};

// ==========================================
//  3. CLASS MANAGER (Full Screen Details)
// ==========================================
const classMgr = {
    // CENTRALIZED VIEW LIST: Ensures we close everything before opening a new one
    views: [
        'cls-view-home',
        'cls-view-roster',
        'cls-view-assigned',
        'cls-view-timetable',
        'cls-view-analytics'
    ],

    async open(classId) {
        state.currentClassId = classId;
        const modal = document.getElementById('modal-manage-class');
        modal.classList.remove('hidden');
        modal.classList.add('flex');

        // Always start at Home
        this.showHome();

        // Load Header Details
        document.getElementById('mng-class-name').textContent = "Loading...";
        document.getElementById('mng-class-batch').textContent = "...";
        document.getElementById('mng-student-count').textContent = "";

        try {
            const res = await fetch(`${window.djangoUrls.getClassStudents}?class_id=${classId}`);
            const data = await res.json();

            if (res.ok) {
                document.getElementById('mng-class-name').textContent = data.className;
                document.getElementById('mng-class-batch').textContent = data.batch;
                document.getElementById('mng-student-count').textContent = `${data.students.length} Students`;

                state.currentRoster = data.students;
                state.currentClassDeptId = data.dept_id;
            }
        } catch (e) { console.error(e); }
    },

    // HELPER: Hides all sections inside the Class Modal
    hideAllViews() {
        this.views.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });
        // Also hide the back button by default
        const backBtn = document.getElementById('btn-back-class-home');
        if (backBtn) backBtn.classList.add('hidden');
    },

    showHome() {
        this.hideAllViews();
        document.getElementById('cls-view-home').classList.remove('hidden');
        // Back button stays hidden on home
    },

    showRoster() {
        this.hideAllViews();
        document.getElementById('cls-view-roster').classList.remove('hidden');
        document.getElementById('btn-back-class-home').classList.remove('hidden');
        this.renderRoster(state.currentRoster || []);
    },

    renderRoster(students) {
        const tbody = document.getElementById('cls-roster-body');
        tbody.innerHTML = '';
        const header = document.createElement('tr');
        header.innerHTML = `<td colspan="4" class="p-2 text-right"><button onclick="classMgr.openAddStudent()" class="text-xs bg-teal-600 text-white px-3 py-1 rounded hover:bg-teal-500 font-bold shadow">+ Add Student</button></td>`;
        tbody.appendChild(header);

        if (!students || students.length === 0) {
            tbody.innerHTML += '<tr><td colspan="4" class="p-4 text-center text-slate-500">No students found.</td></tr>';
            return;
        }

        students.forEach(s => {
            tbody.innerHTML += `
            <tr class="group hover:bg-slate-800/50 transition border-b border-slate-800/50">
                <td class="py-3 pl-2 font-mono text-teal-400">${s.reg_no}</td>
                <td class="py-3 font-medium text-white">${s.name}</td>
                <td class="py-3 text-slate-400 text-xs">${s.email || '-'}</td>
                <td class="py-3 text-right pr-4 flex justify-end gap-2">
                    <button onclick="classMgr.editStudent(${s.id}, '${s.reg_no}', '${s.name}', '${s.email || ''}')" class="p-1.5 bg-blue-900/30 text-blue-400 hover:bg-blue-600 hover:text-white rounded transition"><i data-lucide="pencil" class="w-4 h-4"></i></button>
                    <button onclick="classMgr.deleteStudent(${s.id})" class="p-1.5 bg-red-900/30 text-red-400 hover:bg-red-600 hover:text-white rounded transition"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
                </td>
            </tr>`;
        });
        if (window.lucide) lucide.createIcons();
    },

    editStudent(id, reg, name, email) {
        document.getElementById('edit-stu-id').value = id;
        document.getElementById('edit-stu-reg').value = reg;
        document.getElementById('edit-stu-name').value = name;
        document.getElementById('edit-stu-email').value = email;

        const modal = document.getElementById('modal-edit-student');
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    },

    async saveStudentEdit() {
        const id = document.getElementById('edit-stu-id').value;
        const reg = document.getElementById('edit-stu-reg').value;
        const name = document.getElementById('edit-stu-name').value;
        const email = document.getElementById('edit-stu-email').value;

        if (!reg || !name) return alert("Name and Reg No required");

        try {
            const res = await fetch(window.djangoUrls.editStudent, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify({ student_id: id, reg_no: reg, name: name, email: email })
            });

            if (res.ok) {
                document.getElementById('modal-edit-student').classList.add('hidden');
                // Refresh roster
                const response = await fetch(`${window.djangoUrls.getClassStudents}?class_id=${state.currentClassId}`);
                const data = await response.json();
                state.currentRoster = data.students;
                this.renderRoster(state.currentRoster);
                alert("Student Updated!");
            } else {
                alert("Update Failed");
            }
        } catch (e) { alert("Network Error"); }
    },

    filterRoster() {
        const query = document.getElementById('roster-search-bar').value.toLowerCase();
        const filtered = state.currentRoster.filter(s => s.name.toLowerCase().includes(query) || s.reg_no.toLowerCase().includes(query));
        this.renderRoster(filtered);
    },

    async showAssigned() {
        this.hideAllViews();
        document.getElementById('cls-view-assigned').classList.remove('hidden');
        document.getElementById('btn-back-class-home').classList.remove('hidden');
        const tbody = document.getElementById('cls-assigned-body');
        tbody.innerHTML = '<tr><td colspan="5" class="text-center py-8 text-slate-500">Loading assignments...</td></tr>';

        try {
            const res = await fetch(`${window.djangoUrls.getClassCourses}?class_id=${state.currentClassId}`);
            const data = await res.json();
            tbody.innerHTML = '';

            if (data.courses.length === 0) {
                document.getElementById('no-assigned-msg').classList.remove('hidden');
            } else {
                document.getElementById('no-assigned-msg').classList.add('hidden');
                data.courses.forEach(c => {
                    // Logic for Reassign/Revoke buttons
                    let actionButtons = '';
                    let rowClass = 'hover:bg-slate-800/50';
                    let statusBadge = '';

                    if (c.faculty === 'Unassigned') {
                        rowClass = 'bg-red-900/10 hover:bg-red-900/20 border-l-2 border-red-500';
                        statusBadge = '<span class="ml-2 text-[10px] bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded font-bold uppercase">Orphaned</span>';
                        actionButtons = `
                            <button onclick="resourceMgr.openAssignModal('${c.code}')" class="px-4 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded text-xs font-bold transition flex items-center shadow-lg">
                                <i data-lucide="refresh-cw" class="w-3 h-3 mr-1"></i> Reassign
                            </button>
                        `;
                    } else {
                        actionButtons = `
                            <button onclick="analyticsMgr.openSubjectHub(${c.id})" class="px-3 py-1 bg-emerald-900/30 text-emerald-400 hover:bg-emerald-600 hover:text-white rounded text-xs font-bold transition flex items-center">
                                <i data-lucide="bar-chart-2" class="w-3 h-3 mr-1"></i> Stats
                            </button>
                            <button onclick="classMgr.revokeAssignment(${c.id})" class="p-1.5 bg-red-900/30 text-red-400 hover:bg-red-600 hover:text-white rounded transition">
                                <i data-lucide="trash-2" class="w-4 h-4"></i>
                            </button>
                        `;
                    }

                    tbody.innerHTML += `
                        <tr class="${rowClass} transition group border-b border-slate-800/50">
                            <td class="py-3 pl-4 font-medium text-white">${c.subject}</td>
                            <td class="py-3 font-mono text-amber-400 text-xs">${c.code}</td>
                            <td class="py-3">
                                <span class="text-sm ${c.faculty === 'Unassigned' ? 'text-red-400 italic' : 'text-slate-300'}">${c.faculty}</span>
                                ${statusBadge}
                            </td>
                            <td class="py-3 text-center font-bold text-slate-400">${c.hours}</td>
                            <td class="py-3 text-right pr-4">
                                <div class="flex justify-end gap-2 items-center">
                                    ${actionButtons}
                                </div>
                            </td>
                        </tr>`;
                });
                if (window.lucide) lucide.createIcons();
            }
        } catch (e) { console.error(e); }
    },

    async revokeAssignment(courseId) {
        if (!confirm("Are you sure? This will remove the class from the faculty's dashboard.")) return;
        const formData = new FormData();
        formData.append('course_id', courseId);
        try {
            const res = await fetch(window.djangoUrls.revokeCourse, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken() },
                body: formData
            });
            if (res.ok) {
                alert("Assignment Revoked.");
                this.showAssigned();
            } else {
                const d = await res.json();
                alert("Error: " + (d.error || "Failed"));
            }
        } catch (e) { alert("Network Error"); }
    },
    deleteStudent: function (id) {
        // Correct call:
        dangerMgr.confirmDeleteStudent(id);
    },
};

// ==========================================
//  4. ADMIN NOTIFICATIONS
// ==========================================
const adminNotif = {
    toggle() {
        const dd = document.getElementById('admin-notif-dropdown');
        if (dd.classList.contains('hidden')) { dd.classList.remove('hidden'); this.fetch(); }
        else { dd.classList.add('hidden'); }
    },
    async fetch() {
        try {
            const res = await fetch('/college/notifications/');
            const data = await res.json();
            this.render(data.notifications || []);
        } catch (e) { console.error("Fetch Error", e); }
    },
    render(notifs) {
        const list = document.getElementById('admin-notif-list');
        const badge = document.getElementById('admin-badge');
        if (!list) return;
        list.innerHTML = '';
        if (notifs.length > 0) {
            if (badge) badge.classList.remove('hidden');
            notifs.forEach(n => {
                const item = document.createElement('div');
                item.className = "p-3 hover:bg-slate-800 rounded-lg transition border-b border-slate-800 last:border-0 relative group flex gap-3";
                item.innerHTML = `<div class="mt-1 w-2 h-2 rounded-full bg-blue-500 shrink-0"></div><div class="flex-1"><p class="text-sm text-slate-200 leading-snug">${n.message}</p><p class="text-[10px] text-slate-500 mt-1">${n.date}</p></div><button onclick="adminNotif.markRead(${n.id}, this)" class="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-white transition"><i data-lucide="check" class="w-4 h-4"></i></button>`;
                list.appendChild(item);
            });
            if (window.lucide) lucide.createIcons();
        } else {
            if (badge) badge.classList.add('hidden');
            list.innerHTML = `<div class="flex flex-col items-center justify-center py-6 text-slate-600"><i data-lucide="bell-off" class="w-8 h-8 mb-2 opacity-50"></i><p class="text-xs">No new alerts</p></div>`;
            if (window.lucide) lucide.createIcons();
        }
    },
    async markRead(id, btnElement) {
        const row = btnElement.closest('div');
        row.style.opacity = '0';
        setTimeout(() => row.remove(), 300);
        try {
            await fetch('/college/mark-read/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: id }) });
            if (document.getElementById('admin-notif-list').children.length <= 1) document.getElementById('admin-badge').classList.add('hidden');
        } catch (e) { console.error(e); }
    }
};

// ==========================================
//  5. HELPERS & EXPORTS
// ==========================================
const api = {
    async fetchData() {
        try {
            const res = await fetch(window.djangoUrls.getData);
            const data = await res.json();
            state.departments = data.departments || [];
            state.faculty = data.faculty || [];
            ui.renderDepartments(state.departments);
            if (data.stats) ui.updateProfileStats(data.stats);
        } catch (e) { console.error("API Error", e); }
    },

    async initiateAddDept() {
        const name = document.getElementById('inp-dept-name').value.trim();
        if (!name) return alert("Please enter Department Name");

        const btn = document.getElementById('btn-req-otp-dept');
        const ogText = btn.innerHTML;
        btn.innerHTML = "Sending...";
        btn.disabled = true;

        try {
            const res = await fetch(window.djangoUrls.sendAddDeptOtp, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken() }
            });

            if (res.ok) {
                // Success: Switch UI to Step 2
                document.getElementById('add-dept-step-1').classList.add('hidden');
                document.getElementById('add-dept-step-2').classList.remove('hidden');
            } else {
                alert("Failed to send OTP. Please try again.");
            }
        } catch (e) {
            console.error(e);
            alert("Network Error");
        } finally {
            btn.innerHTML = ogText;
            btn.disabled = false;
        }
    },

    // 3. STEP 2: Verify OTP & Create Department
    async verifyAndCreateDept() {
        const otp = document.getElementById('inp-dept-otp').value.trim();
        const name = document.getElementById('inp-dept-name').value.trim();
        const year = document.getElementById('inp-dept-year').value;

        if (otp.length < 4) return alert("Enter valid OTP");

        const btn = document.getElementById('btn-create-dept');
        const ogText = btn.innerText;
        btn.innerText = "Verifying...";
        btn.disabled = true;

        try {
            // A. Verify OTP
            const verifyRes = await fetch(window.djangoUrls.verifyAddDeptOtp, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify({ otp: otp })
            });

            if (!verifyRes.ok) {
                throw new Error("Invalid OTP");
            }

            // B. Create Department (Now that session is verified)
            const formData = new FormData();
            formData.append('name', name);
            formData.append('year', year);

            const createRes = await fetch(window.djangoUrls.addDepartment, {
                method: 'POST',
                headers: { 'X-CSRFToken': getCsrfToken() },
                body: formData
            });

            const data = await createRes.json();

            if (createRes.ok) {
                alert("Department Created Successfully! 🎉");
                modals.close('modal-add-dept');
                this.resetAddDeptModal(); // Reset UI for next time
                this.fetchData(); // Refresh Dashboard Grid
            } else {
                alert("Error: " + data.error);
            }

        } catch (e) {
            console.error(e);
            alert(e.message || "Process Failed");
        } finally {
            btn.innerText = ogText;
            btn.disabled = false;
        }
    },

    // 4. Helper to Reset Modal State
    resetAddDeptModal() {
        document.getElementById('add-dept-step-1').classList.remove('hidden');
        document.getElementById('add-dept-step-2').classList.add('hidden');
        document.getElementById('inp-dept-name').value = '';
        document.getElementById('inp-dept-otp').value = '';
    },

    getClassDetails(classId) { classMgr.open(classId); },

    async fetchAdminStudentProfile(studentId) {
        try {
            const url = window.djangoUrls.getAdminStudentProfile.replace('0', studentId);
            const res = await fetch(url);
            if (!res.ok) throw new Error('Failed to fetch student profile');
            return await res.json();
        } catch (e) { console.error(e); return null; }
    },

    async fetchClassStudentsAll(classId) {
        try {
            const url = `${window.djangoUrls.getClassStudentsAdminAll}?class_id=${classId}`;
            const res = await fetch(url);
            if (!res.ok) throw new Error('Failed to fetch class students');
            return await res.json();
        } catch (e) { console.error(e); return null; }
    },

    exportDeletedStudentsCsv(classId) {
        try {
            const url = window.djangoUrls.exportDeletedStudentsCsv.replace('0', classId);
            window.location.href = url;
        } catch (e) { console.error(e); }
    }
    ,
    // Fetch and display deleted students for the selected class
    async viewDeletedStudentsForSelectedClass() {
        try {
            const sel = document.getElementById('students-class-select');
            if (!sel) return alert('Select a class first');
            const classId = sel.value;
            if (!classId) return alert('Please select a class');

            const url = `${window.djangoUrls.getDeletedStudents}?class_id=${encodeURIComponent(classId)}`;
            const res = await fetch(url);
            if (!res.ok) throw new Error('Failed to fetch deleted students');
            const data = await res.json();
            const container = document.getElementById('deleted-students-list');
            if (!container) return;
            container.innerHTML = '';

            if (!data.students || data.students.length === 0) {
                container.innerHTML = '<p class="text-center text-slate-500 py-6">No deleted students for this class.</p>';
            } else {
                data.students.forEach(s => {
                    const div = document.createElement('div');
                    div.className = 'p-3 border-b border-slate-800 last:border-0 flex items-center justify-between gap-3';
                    div.innerHTML = `
                        <div>
                          <div class="font-bold text-white">${s.name} <span class="text-xs text-slate-500 font-mono">${s.reg_no}</span></div>
                          <div class="text-xs text-slate-400">Joined: ${s.joined_at || '-'} • Overall: ${s.overall_pct}%</div>
                        </div>
                        <div class="flex items-center gap-2">
                          <button class="px-3 py-1 bg-teal-600 hover:bg-teal-500 text-white rounded text-xs font-bold" onclick="(async function(){const d=await api.fetchAdminStudentProfile(${s.id}); if(d) api.showStudentProfile(d);})();">View Profile</button>
                        </div>
                    `;
                    container.appendChild(div);
                });
            }

            document.getElementById('modal-deleted-students').classList.remove('hidden');
            document.getElementById('modal-deleted-students').classList.add('flex');
        } catch (e) { console.error(e); alert('Unable to load deleted students'); }
    },

    // Render admin student profile in the existing student-profile-modal
    async showStudentProfile(data) {
        try {
            if (!data) return;
            document.getElementById('profile-name').textContent = data.name || '';
            document.getElementById('profile-reg').textContent = data.reg_no || '';
            document.getElementById('profile-class').textContent = '';
            document.getElementById('profile-total').textContent = data.overall?.total_hours || 0;
            document.getElementById('profile-present').textContent = data.overall?.present_hours || 0;
            document.getElementById('profile-od').textContent = data.od_hours || 0;
            document.getElementById('profile-absent').textContent = data.absent_hours || 0;
            document.getElementById('profile-percent').textContent = (data.overall?.percentage || 0) + '%';
            const badge = document.getElementById('profile-status-badge');
            if (badge) badge.textContent = (data.overall?.percentage >= 75 ? 'Safe Zone' : 'Critical');

            // Calculate safe skip calculator
            const totalHours = data.overall?.total_hours || 0;
            const attendedHours = (data.overall?.present_hours || 0) + (data.od_hours || 0);
            const requiredHours = totalHours * 0.75;
            const safeSkipHours = Math.max(0, requiredHours - attendedHours);

            let calcText = '';
            if (safeSkipHours > 0) {
                // Assume average class duration of 1 hour for calculation
                const safeSkipClasses = Math.floor(safeSkipHours);
                calcText = `You can safely skip ${safeSkipClasses} more hour(s) of classes while maintaining 75% attendance.`;
            } else {
                calcText = `You are already below 75% attendance. Attend all remaining classes to improve your percentage.`;
            }

            const calcElement = document.getElementById('skip-calc-result');
            if (calcElement) calcElement.textContent = calcText;

            // Draw per-course chart if present
            if (data.per_course) {
                // Ensure a canvas exists in modal (create if necessary)
                let canvas = document.getElementById('studentCourseBar');
                if (!canvas) {
                    const container = document.querySelector('#student-profile-modal .overflow-y-auto');
                    if (container) {
                        const wrapper = document.createElement('div');
                        wrapper.className = 'mt-6 pt-6 border-t border-slate-700';
                        wrapper.innerHTML = `
                          <h3 class="text-sm font-bold text-slate-300 mb-3">Subject-wise Hours</h3>
                          <div class="bg-slate-900 p-3 rounded-lg border border-slate-700"><canvas id="studentCourseBar" style="height:180px; width:100%"></canvas></div>`;
                        container.appendChild(wrapper);
                    }
                    canvas = document.getElementById('studentCourseBar');
                }

                // Draw chart
                try {
                    if (window._studentProfileChart) { window._studentProfileChart.destroy(); window._studentProfileChart = null; }
                    const labels = data.per_course.map(p => p.subject + (p.code ? ` (${p.code})` : ''));
                    const presentData = data.per_course.map(p => Number(p.present_hours) || 0);
                    const odData = data.per_course.map(p => Number(p.od_hours) || 0);
                    const absentData = data.per_course.map(p => Number(p.absent_hours) || 0);

                    // Calculate max value for proper Y-axis scaling
                    const allValues = [...presentData, ...odData, ...absentData];
                    const maxValue = Math.max(...allValues, 1);

                    const ctx = document.getElementById('studentCourseBar').getContext('2d');
                    window._studentProfileChart = new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: labels.length ? labels : ['No Data'],
                            datasets: [
                                {
                                    label: 'Present',
                                    data: presentData,
                                    backgroundColor: '#16a34a',
                                    borderColor: '#16a34a',
                                    borderWidth: 1,
                                    barThickness: 20
                                },
                                {
                                    label: 'On Duty',
                                    data: odData,
                                    backgroundColor: '#3b82f6',
                                    borderColor: '#3b82f6',
                                    borderWidth: 1,
                                    barThickness: 20
                                },
                                {
                                    label: 'Absent',
                                    data: absentData,
                                    backgroundColor: '#ef4444',
                                    borderColor: '#ef4444',
                                    borderWidth: 1,
                                    barThickness: 20
                                }
                            ]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { position: 'bottom' },
                                tooltip: {
                                    callbacks: {
                                        label: function(context) {
                                            return context.dataset.label + ': ' + context.parsed.y + ' hours';
                                        }
                                    }
                                }
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    min: 0,
                                    max: maxValue + 5, // Add some padding
                                    title: {
                                        display: true,
                                        text: 'Hours'
                                    },
                                    ticks: {
                                        stepSize: 1, // Force integer steps
                                        callback: function(value) {
                                            return Number.isInteger(value) ? value + ' hrs' : '';
                                        }
                                    }
                                },
                                x: {
                                    title: {
                                        display: true,
                                        text: 'Courses'
                                    },
                                    ticks: {
                                        maxRotation: 45,
                                        minRotation: 45
                                    }
                                }
                            }
                        }
                    });
                } catch (e) { console.error('Chart error', e); }
            }

            // Open modal
            document.getElementById('student-profile-modal').classList.remove('hidden');
            document.getElementById('student-profile-modal').classList.add('flex');
        } catch (e) { console.error(e); }
    }
};
const modals = {
    openAddDept() {
        ui.populateYearDropdown();
        api.resetAddDeptModal(); // Ensure clean state
        document.getElementById('modal-add-dept').classList.remove('hidden');
        document.getElementById('modal-add-dept').classList.add('flex');
    },
    openManageDept(deptId) { resourceMgr.open(deptId); },
    close(id) { document.getElementById(id).classList.add('hidden'); document.getElementById(id).classList.remove('flex'); }
};

const analyticsMgr = {
    data: null,
    currentCourseId: null,
    charts: {},

    // 1. Admin Mode
    openHub() {
        this.currentCourseId = null;
        this.loadView();
    },

    // 2. Faculty Mode
    openSubjectHub(courseId) {
        this.currentCourseId = courseId;
        this.loadView();
    },

    loadView() {
        // --- KEY FIX: Hide Home Buttons ---
        classMgr.hideAllViews();

        document.getElementById('cls-view-analytics').classList.remove('hidden');
        document.getElementById('btn-back-class-home').classList.remove('hidden');

        document.getElementById('metric-total-students').textContent = "...";
        this.fetchData();
    },

    async fetchData() {
        try {
            if (!state.currentClassId) return alert("Class ID missing");

            let url = `${window.djangoUrls.classAnalytics}?class_id=${state.currentClassId}`;
            if (this.currentCourseId) {
                url += `&course_id=${this.currentCourseId}`;
            }

            const res = await fetch(url);
            if (!res.ok) {
                throw new Error(`HTTP Error: ${res.status}`);
            }
            const data = await res.json();
            if (data.error) {
                throw new Error(data.error);
            }
            this.data = data;

            // If modal is currently open, refresh the view
            if (!document.getElementById('metrics-modal').classList.contains('hidden')) {
                this.updateMetricsUI();
            }
        } catch (e) {
            console.error("Analytics Error", e);
            alert("Error loading analytics: " + e.message);
        }
    },

    showMetrics() {
        if (!this.data) return alert("Loading data...");
        const modal = document.getElementById('metrics-modal');
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        this.updateMetricsUI();
        requestAnimationFrame(() => this.renderCharts());
    },

    updateMetricsUI() {
        if (!this.data) return;

        document.getElementById('analytics-modal-title').textContent = this.data.meta.title;
        document.getElementById('analytics-modal-subtitle').textContent = this.data.meta.subtitle;

        const facEl = document.getElementById('analytics-faculty-name');
        if (facEl) {
            if (this.data.meta.faculty_name) {
                facEl.textContent = this.data.meta.faculty_name;
                facEl.classList.remove('hidden');
            } else {
                facEl.classList.add('hidden');
            }
        }

        document.getElementById('metric-total-students').textContent = this.data.stats.total_students;
        document.getElementById('metric-total-sessions').textContent = this.data.stats.total_sessions;
        document.getElementById('metric-total-hours').textContent = this.data.stats.total_hours;

        const historySec = document.getElementById('analytics-history-section');
        if (this.currentCourseId) {
            historySec.classList.remove('hidden');
            this.renderHistoryTable();
        } else {
            historySec.classList.add('hidden');
        }
    },

    renderHistoryTable() {
        const tbody = document.getElementById('analytics-history-body');
        tbody.innerHTML = '';
        const history = this.data.history || [];

        if (history.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-slate-500">No session history found.</td></tr>';
            return;
        }

        history.forEach(rec => {
            try {
                const p = rec.present || 0;
                const od = rec.od || 0;
                const a = rec.absent || 0;
                const total = p + od + a;
                const pct = total > 0 ? Math.round(((p + od) / total) * 100) : 0;
                let pctClass = 'text-green-400';
                if (pct < 75) pctClass = 'text-red-400';
                else if (pct < 85) pctClass = 'text-amber-400';

                tbody.innerHTML += `
                    <tr class="hover:bg-slate-800/50 transition">
                        <td class="p-4 font-mono text-slate-300">${rec.date}</td>
                        <td class="p-4 text-center"><span class="bg-slate-800 px-2 py-1 rounded text-xs border border-slate-700">S: ${rec.session}</span></td>
                        <td class="p-4 text-center text-xs">
                            <span class="text-green-400">P:${p}</span> / <span class="text-blue-400">OD:${od}</span> / <span class="text-red-400">A:${a}</span>
                        </td>
                        <td class="p-4 text-right font-bold ${pctClass}">${pct}%</td>
                    </tr>
                `;
            } catch (e) {
                console.error("Error rendering history row:", rec, e);
            }
        });
    },

    renderCharts() {
        let pieLabels, pieColors, trendLabel, trendColor;

        if (this.currentCourseId) {
            pieLabels = ['Present', 'On Duty', 'Absent'];
            pieColors = ['#10b981', '#3b82f6', '#ef4444'];
            trendLabel = 'Daily Attendance %';
            trendColor = '#14b8a6';
        } else {
            pieLabels = ['Safe Zone', 'Defaulters'];
            pieColors = ['#10b981', '#ef4444'];
            trendLabel = 'Avg Class Attendance %';
            trendColor = '#8b5cf6';
        }

        const ctxPie = document.getElementById('adminPieChart');
        if (ctxPie) {
            if (this.charts.pie) this.charts.pie.destroy();
            this.charts.pie = new Chart(ctxPie.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: pieLabels,
                    datasets: [{
                        data: this.data.charts.pie_data,
                        backgroundColor: pieColors,
                        borderWidth: 0,
                        hoverOffset: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8' } } }
                }
            });
        }

        const ctxTrend = document.getElementById('adminTrendChart');
        if (ctxTrend) {
            if (this.charts.trend) this.charts.trend.destroy();
            this.charts.trend = new Chart(ctxTrend.getContext('2d'), {
                type: 'line',
                data: {
                    labels: this.data.charts.trend_labels,
                    datasets: [{
                        label: trendLabel,
                        data: this.data.charts.trend_data,
                        borderColor: trendColor,
                        backgroundColor: (context) => {
                            const ctx = context.chart.ctx;
                            if (context.chart.height === 0) return `${trendColor}33`;
                            try {
                                const gradient = ctx.createLinearGradient(0, 0, 0, 300);
                                gradient.addColorStop(0, `${trendColor}33`);
                                gradient.addColorStop(1, `${trendColor}00`);
                                return gradient;
                            } catch (e) { return `${trendColor}33`; }
                        },
                        fill: true,
                        tension: 0.4,
                        pointRadius: 3,
                        pointBackgroundColor: '#0f172a'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, max: 100, grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
                        x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
                    },
                    plugins: { legend: { display: false } },
                    interaction: { mode: 'index', intersect: false }
                }
            });
        }
    },

    showDefaulters() {
        if (!this.data) return;
        document.getElementById('defaulters-modal').classList.remove('hidden');
        document.getElementById('defaulters-modal').classList.add('flex');
        const title = this.data.meta.course_id ? `Subject: ${this.data.meta.title}` : `Overall Class`;
        document.getElementById('defaulter-class-name').textContent = title;
        const tbody = document.getElementById('defaulters-table-body');
        const emptyMsg = document.getElementById('no-defaulters-msg');
        tbody.innerHTML = '';

        if (this.data.defaulters.length === 0) {
            emptyMsg.classList.remove('hidden');
        } else {
            emptyMsg.classList.add('hidden');
            this.data.defaulters.forEach(s => {
                const isCritical = s.severity === 'Critical';
                const badgeColor = isCritical ? 'bg-red-900/50 text-red-400 border-red-800' : 'bg-amber-900/50 text-amber-400 border-amber-800';
                tbody.innerHTML += `
                    <tr class="border-b border-slate-700/50 hover:bg-slate-700/30">
                        <td class="p-3 text-teal-400 font-mono">${s.reg_no}</td>
                        <td class="p-3 text-white font-bold">${s.name}</td>
                        <td class="p-3 text-center text-slate-300">${s.present}/${s.total}</td>
                        <td class="p-3 text-center font-bold ${isCritical ? 'text-red-500' : 'text-amber-500'}">${s.percent}%</td>
                        <td class="p-3 text-center"><span class="px-2 py-1 rounded text-xs border ${badgeColor}">${s.severity}</span></td>
                    </tr>`;
            });
        }
    },

    showLeaderboard() {
        if (!this.data) return;
        document.getElementById('leaderboard-modal').classList.remove('hidden');
        document.getElementById('leaderboard-modal').classList.add('flex');
        const container = document.getElementById('leaderboard-list');
        container.innerHTML = '';
        this.data.leaderboard.forEach((s, i) => {
            let badge = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${i + 1}`;
            container.innerHTML += `
                <div class="flex items-center justify-between p-3 bg-slate-700/30 rounded-lg border border-slate-700 mb-2">
                    <div class="flex items-center gap-3">
                        <span class="text-xl font-bold w-8 text-center">${badge}</span>
                        <div><p class="font-bold text-white">${s.name}</p><p class="text-xs text-slate-500">${s.reg_no}</p></div>
                    </div>
                    <p class="text-emerald-400 font-bold">${s.percent}%</p>
                </div>`;
        });
    },

    showColdCall() {
        if (!this.data || this.data.stats.total_students === 0) return alert("No students found.");
        document.getElementById('cold-call-modal').classList.remove('hidden');
        document.getElementById('cold-call-modal').classList.add('flex');
        document.getElementById('cold-call-display').textContent = "Ready?";
        document.getElementById('cold-call-display').className = "text-3xl font-bold text-slate-500 h-12 flex items-center justify-center";
        document.getElementById('cold-call-reg').classList.add('opacity-0');

        const btn = document.getElementById('spin-wheel-btn');
        btn.onclick = () => {
            // Need student list for this. If not in 'data', use 'currentRoster'
            const list = state.currentRoster || [];
            if (list.length === 0) return alert("Roster empty");
            let i = 0;
            const interval = setInterval(() => {
                const r = list[Math.floor(Math.random() * list.length)];
                document.getElementById('cold-call-display').textContent = r.name;
                i++;
                if (i > 20) {
                    clearInterval(interval);
                    document.getElementById('cold-call-display').classList.add('text-pink-500', 'scale-110');
                    document.getElementById('cold-call-reg').textContent = r.reg_no;
                    document.getElementById('cold-call-reg').classList.remove('opacity-0');
                }
            }, 80);
        };
    },

    showReports() {
        document.getElementById('download-report-modal').classList.remove('hidden');
        document.getElementById('download-report-modal').classList.add('flex');

        // REQ 5: Handle 2 Report Types
        document.getElementById('confirm-download-btn').onclick = () => {
            const reportType = document.querySelector('input[name="report-type"]:checked').value;

            let url = "";
            if (reportType === 'master') {
                // Overall Class Report
                url = window.djangoUrls.exportAdminMaster.replace('0', state.currentClassId);
            } else if (this.currentCourseId) {
                // Specific Subject Report (Detailed)
                url = window.djangoUrls.exportAdminCourse.replace('0', this.currentCourseId);
            } else {
                return alert("For detailed reports, please select a specific subject/class card first, or choose 'Master Sheet'.");
            }
            window.location.href = url;
        };
    }
};


// CRITICAL: Expose to window
window.analyticsMgr = analyticsMgr;

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

// Student Manager: Admin-side student search & profile display
const studentMgr = {
    currentClassId: null,
    async init() {
        // populate class select
        const sel = document.getElementById('students-class-select');
        if (!sel) return;
        sel.innerHTML = '<option value="">-- Select Class --</option>';
        if (!state.departments) return;
        state.departments.forEach(d => {
            if (d.classes && d.classes.length) {
                d.classes.forEach(c => {
                    const opt = document.createElement('option');
                    opt.value = c.id;
                    opt.textContent = `${d.name} • ${c.name}`;
                    sel.appendChild(opt);
                });
            }
        });

        sel.onchange = () => { this.currentClassId = sel.value || null; };
    },

    async searchByReg() {
        const reg = document.getElementById('student-search-reg').value.trim();
        const results = document.getElementById('student-search-results');
        results.innerHTML = '';
        if (!reg) return results.innerHTML = '<p class="text-slate-500">Enter a register number.</p>';

        // Loading UI
        const searchBtn = document.querySelector('#view-students button[onclick="studentMgr.searchByReg()"]');
        if (searchBtn) { searchBtn.disabled = true; searchBtn.dataset.orig = searchBtn.textContent; searchBtn.textContent = 'Searching...'; }
        results.innerHTML = '<p class="text-slate-500">Searching<span id="student-search-spinner">⏳</span></p>';

        try {
            let data = null;
            if (this.currentClassId) {
                data = await api.fetchClassStudentsAll(this.currentClassId);
                if (!data || !data.students) return results.innerHTML = '<p class="text-slate-500">No students found for this class.</p>';
            } else {
                // No class selected: scan all classes in state
                const classIds = [];
                if (state.departments && state.departments.length) {
                    state.departments.forEach(d => { if (d.classes) d.classes.forEach(c => classIds.push(c.id)); });
                }
                if (classIds.length === 0) return results.innerHTML = '<p class="text-slate-500">No classes available to search.</p>';

                const promises = classIds.map(id => api.fetchClassStudentsAll(id));
                const all = await Promise.all(promises);
                data = { students: [] };
                all.forEach(item => { if (item && item.students) data.students = data.students.concat(item.students); });
            }

            const found = data.students.find(s => (s.reg_no || '').toLowerCase() === reg.toLowerCase());
            if (!found) return results.innerHTML = `<p class="text-slate-500">Student ${reg} not found.</p>`;

            // Fetch detailed profile
            const profile = await api.fetchAdminStudentProfile(found.id);
            if (!profile) return results.innerHTML = '<p class="text-slate-500">Failed to load profile.</p>';

            // Render a summary and a button to view full modal
            results.innerHTML = `
                <div class="flex items-center justify-between">
                    <div>
                        <h3 class="text-white font-bold">${profile.name}</h3>
                        <p class="text-slate-400 text-sm font-mono">${profile.reg_no} • ${profile.email || ''}</p>
                    </div>
                    <div class="flex gap-2">
                        <button class="bg-teal-600 hover:bg-teal-500 text-white px-3 py-2 rounded" onclick="studentMgr.showProfileModal(${profile.id})">View Full Profile</button>
                    </div>
                </div>
                <div class="mt-4 grid grid-cols-3 gap-2">
                    <div class="bg-slate-900 p-2 rounded text-center"><p class="text-xs text-slate-400">Present Hrs</p><p class="text-white font-bold">${profile.overall.present_hours}</p></div>
                    <div class="bg-slate-900 p-2 rounded text-center"><p class="text-xs text-slate-400">OD Hrs</p><p class="text-white font-bold">${profile.od_hours}</p></div>
                    <div class="bg-slate-900 p-2 rounded text-center"><p class="text-xs text-slate-400">Absent Hrs</p><p class="text-white font-bold">${profile.absent_hours}</p></div>
                </div>
            `;
        } finally {
            if (searchBtn) { searchBtn.disabled = false; searchBtn.textContent = searchBtn.dataset.orig || 'Search'; }
        }
    },

    showProfileModal(studentId) {
        api.fetchAdminStudentProfile(studentId).then(profile => {
            if (!profile) return alert('Failed to fetch profile');
            api.showStudentProfile(profile);
        });
    },

    exportDeletedForSelectedClass() {
        if (!this.currentClassId) return alert('Select a class first');
        api.exportDeletedStudentsCsv(this.currentClassId);
    }
};

// --- DANGER MANAGER (OTP Deletions) ---
const dangerMgr = {
    targetType: null,
    targetId: null,
    pendingAction: null,

    confirmDelete(type, id) {
        this.targetType = type;
        this.targetId = id;
        document.getElementById('modal-danger-otp').classList.remove('hidden');
        document.getElementById('modal-danger-otp').classList.add('flex');

        const txt = type === 'dept' ? 'Entire Department' : 'Class';
        document.getElementById('danger-msg').textContent = `Deleting ${txt} is permanent. OTP required.`;

        document.getElementById('danger-step-1').classList.remove('hidden');
        document.getElementById('danger-step-2').classList.add('hidden');
    },
    // 3. Confirm Delete Class
    confirmDeleteClass(classId) {
        this.pendingAction = {
            action_type: 'class',
            target_id: classId
        };
        this.openOtpModal("Confirm Class Deletion");
    },
    confirmDeleteStudent(studentId) {
        // Prepare the action data
        this.pendingAction = {
            action_type: 'student',
            target_id: studentId
        };
        // CRITICAL FIX: Call the modal opener, DO NOT call confirmDeleteStudent again
        this.openOtpModal("Confirm Student Removal");
    },

    // 2. CONFIRM TERMINATE FACULTY
    confirmTerminateFaculty() {
        const replacementId = document.getElementById('term-replacement-select').value;
        const facultyId = facultyMgr.currentId;

        this.pendingAction = {
            action_type: 'faculty',
            target_id: facultyId,
            extra_data: { replacement_id: replacementId }
        };

        document.getElementById('modal-faculty-details').classList.add('hidden');
        this.openOtpModal("Confirm Faculty Termination");
    },

    // 3. CONFIRM DELETE CLASS
    confirmDeleteClass(classId) {
        this.pendingAction = {
            action_type: 'class',
            target_id: classId
        };
        this.openOtpModal("Confirm Class Deletion");
    },

    // --- SHARED OTP MODAL LOGIC ---
    openOtpModal(title) {
        // This line caused your error. It works now because you added the ID in HTML.
        const titleEl = document.getElementById('danger-modal-title');
        if (titleEl) titleEl.textContent = title;

        document.getElementById('modal-danger-otp').classList.remove('hidden');
        document.getElementById('modal-danger-otp').classList.add('flex');

        // Reset Steps
        document.getElementById('danger-step-1').classList.remove('hidden');
        document.getElementById('danger-step-2').classList.add('hidden');
        document.getElementById('danger-otp-input').value = '';
    },

    async sendOtp() {
        const btn = document.querySelector('#danger-step-1 button');
        const ogText = btn.textContent;
        btn.disabled = true; btn.textContent = "Sending...";

        try {
            const res = await fetch(window.djangoUrls.sendActionOtp, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify(this.pendingAction)
            });

            if (res.ok) {
                document.getElementById('danger-step-1').classList.add('hidden');
                document.getElementById('danger-step-2').classList.remove('hidden');
                alert("OTP Sent to Admin Email");
            } else {
                alert("Failed to send OTP");
            }
        } catch (e) { console.error(e); }
        finally { btn.disabled = false; btn.textContent = ogText; }
    },

    async verifyAndExecute() {
        const otp = document.getElementById('danger-otp-input').value;
        if (otp.length < 4) return alert("Enter valid OTP");

        try {
            const res = await fetch(window.djangoUrls.verifyActionOtp, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify({ otp: otp })
            });

            const data = await res.json();

            if (res.ok) {
                alert(data.message);
                document.getElementById('modal-danger-otp').classList.add('hidden');

                // Refresh UI based on what we just deleted
                if (this.pendingAction.action_type === 'student') {
                    // Reload the class roster to show the student is gone
                    if (classMgr && state.currentClassId) classMgr.open(state.currentClassId);
                }
                else if (this.pendingAction.action_type === 'class') api.fetchData();
                else if (this.pendingAction.action_type === 'faculty') api.fetchData();
            } else {
                alert("Error: " + data.error);
            }
        } catch (e) { console.error(e); }
    }

};

// --- FACULTY TERMINATION MANAGER ---
const facultyMgr = {
    currentId: null,
    async openDetails(id) {
        this.currentId = id;

        // 1. Fetch Details
        const res = await fetch(`${window.djangoUrls.getFacDetails}?faculty_id=${id}`);
        const data = await res.json();

        document.getElementById('modal-faculty-details').classList.remove('hidden');
        document.getElementById('modal-faculty-details').classList.add('flex');

        document.getElementById('term-fac-name').textContent = data.name;
        document.getElementById('term-fac-email').textContent = data.email;
        document.getElementById('term-fac-initials').textContent = data.name.substring(0, 2).toUpperCase();

        // 2. RENDER COURSE LIST WITH BADGES
        const list = document.getElementById('term-fac-courses');
        list.innerHTML = '';

        if (data.assigned_courses.length === 0) {
            list.innerHTML = '<li class="text-slate-500 italic text-xs">No active classes</li>';
        } else {
            data.assigned_courses.forEach(c => {
                // Determine Badge Logic
                let badge = c.is_official
                    ? `<span class="text-[10px] bg-teal-900/50 text-teal-400 px-1.5 py-0.5 rounded border border-teal-700/50 font-bold uppercase tracking-wider">Official</span>`
                    : `<span class="text-[10px] bg-purple-900/50 text-purple-400 px-1.5 py-0.5 rounded border border-purple-700/50 font-bold uppercase tracking-wider">Personal</span>`;

                list.innerHTML += `
                    <li class="flex items-center justify-between py-1 border-b border-slate-800 last:border-0">
                        <span class="text-slate-300 truncate pr-2" title="${c.title}">${c.title}</span>
                        ${badge}
                    </li>`;
            });
        }

        // ... (Rest of your existing Replacement Dropdown logic) ...
        const select = document.getElementById('term-replacement-select');
        select.innerHTML = '<option value="">-- Do not transfer (Unassign) --</option>';

        if (state.faculty && state.faculty.length > 0) {
            state.faculty.forEach(f => {
                if (f.id !== id) {
                    select.innerHTML += `<option value="${f.id}">${f.name} (${f.department})</option>`;
                }
            });
        }
    },

    async terminate() {
        const replacementId = document.getElementById('term-replacement-select').value;
        const msg = replacementId
            ? "⚠️ Confirm Transfer: All classes and attendance data will be moved to the new faculty member."
            : "⚠️ Warning: You selected 'No Transfer'. Classes will become unassigned.";

        if (!confirm(msg + "\n\nAre you sure you want to terminate this faculty?")) return;

        // Route through OTP verification instead of direct termination
        dangerMgr.confirmTerminateFaculty();
    }
};

const timetableMgr = {
    config: null,
    selectedSubject: null,

    async open(classId) {
        if (!classId || classId === 'null') {
            alert("Error: Please select a class first.");
            return;
        }
        state.currentClassId = classId;

        // 1. CLEAN UI: Hide other views
        classMgr.hideAllViews();
        document.getElementById('cls-view-timetable').classList.remove('hidden');
        document.getElementById('btn-back-class-home').classList.remove('hidden');

        // 2. Set Header
        const nameEl = document.getElementById('mng-class-name');
        if (nameEl) document.getElementById('tt-class-name').textContent = nameEl.textContent;

        await this.loadData();
    },

    async loadData() {
        const res = await fetch(`${window.djangoUrls.initTimetable}?class_id=${state.currentClassId}`);
        this.config = await res.json();

        if (!this.config || !this.config.subjects) {
            console.error("Invalid config loaded", this.config);
            return;
        }

        document.getElementById('tt-weeks-disp').textContent = this.config.weeks_available;
        this.renderPalette();
        this.renderGrid();
    },

    renderPalette() {
        const container = document.getElementById('tt-subject-list');
        container.innerHTML = '';
        const subjects = this.config?.subjects || [];

        if (subjects.length === 0) {
            container.innerHTML = '<p class="text-slate-500 text-xs p-4">No subjects found.</p>';
            return;
        }

        subjects.forEach((sub, index) => {
            const el = document.createElement('div');
            // Style logic
            if (sub.status === 'unassigned') {
                el.className = "bg-slate-800/50 p-3 rounded-lg border border-slate-700 opacity-60 cursor-not-allowed relative mb-2";
                el.onclick = () => alert(`Subject '${sub.name}' is not assigned to this class yet.`);
            } else {
                el.className = "bg-slate-900 p-3 rounded-lg border border-slate-700 cursor-pointer hover:border-teal-500 transition group relative mb-2";
                el.onclick = (e) => {
                    if (!e.target.closest('button')) this.selectSubject(sub, el);
                };
            }

            el.innerHTML = `
                <div class="flex justify-between items-start">
                    <div>
                        <h4 class="font-bold text-white text-sm">${sub.code}</h4>
                        <p class="text-[10px] text-slate-400 truncate w-32">${sub.name}</p>
                        <p class="text-[10px] ${sub.status === 'unassigned' ? 'text-red-400' : 'text-teal-400'} mt-1 flex items-center gap-1">
                            <i data-lucide="${sub.status === 'unassigned' ? 'alert-circle' : 'user'}" class="w-3 h-3"></i> ${sub.faculty}
                        </p>
                    </div>
                    
                    <div class="text-right flex flex-col items-end">
                         ${sub.status === 'active' ?
                    `<div class="flex items-center gap-2 mb-1 bg-slate-800 rounded p-1">
                                <button onclick="timetableMgr.adjustHours(${index}, -1)" class="text-slate-400 hover:text-white px-1 hover:bg-slate-700 rounded transition">-</button>
                                <span class="text-sm font-bold text-white w-4 text-center">${sub.weekly_hours_needed}</span>
                                <button onclick="timetableMgr.adjustHours(${index}, 1)" class="text-slate-400 hover:text-white px-1 hover:bg-slate-700 rounded transition">+</button>
                            </div>
                            <span class="text-[9px] uppercase text-slate-600">Hrs/Wk</span>`
                    :
                    `<span class="text-[9px] uppercase text-slate-500 bg-slate-800 px-1 rounded">N/A</span>`
                }
                    </div>
                </div>
            `;
            container.appendChild(el);
        });
        if (window.lucide) lucide.createIcons();
    },

    selectSubject(sub, el) {
        document.querySelectorAll('#tt-subject-list > div').forEach(d => d.classList.remove('ring-2', 'ring-teal-500'));
        el.classList.add('ring-2', 'ring-teal-500');
        this.selectedSubject = sub;
    },

    renderGrid() {
        const header = document.getElementById('tt-grid-header');
        header.innerHTML = '<th class="p-3 bg-slate-900 text-slate-500 text-xs uppercase w-24">Day</th>';
        for (let i = 1; i <= this.config.periods; i++) {
            header.innerHTML += `<th class="p-3 bg-slate-900 text-slate-300 text-sm border-l border-slate-700">Period ${i}</th>`;
        }

        const body = document.getElementById('tt-grid-body');
        body.innerHTML = '';
        const days = this.config.working_days;

        days.forEach(day => {
            const row = document.createElement('tr');
            row.innerHTML = `<td class="p-4 bg-slate-900 font-bold text-slate-400 border-b border-slate-800">${day.substring(0, 3)}</td>`;

            for (let i = 1; i <= this.config.periods; i++) {
                const existing = this.config.existing_slots.find(s => s.day === day && s.period_number === i);
                const cellContent = existing ? `<span class="text-xs font-bold text-teal-400 bg-teal-900/20 px-2 py-1 rounded">${existing.subject__subject_code}</span>` : '<span class="text-slate-600 text-xs opacity-0 hover:opacity-100">+ Add</span>';

                row.innerHTML += `
                    <td onclick="timetableMgr.assignSlot(this, '${day}', ${i})" 
                        class="p-2 border border-slate-700/50 text-center cursor-pointer hover:bg-slate-700/50 transition relative h-16 w-32">
                        ${cellContent}
                    </td>`;
            }
            body.appendChild(row);
        });
    },

    async assignSlot(cell, day, period) {
        if (!this.selectedSubject) return alert("Select a subject from the list first.");
        cell.innerHTML = '<span class="text-xs text-amber-400 animate-pulse">Checking...</span>';

        try {
            // 1. Conflict Check
            const checkRes = await fetch(window.djangoUrls.checkConflict, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify({
                    faculty_id: this.selectedSubject.faculty_id,
                    day: day, period: period, class_id: state.currentClassId
                })
            });
            const checkData = await checkRes.json();

            if (checkData.conflict) {
                alert("⚠️ " + checkData.message);
                cell.innerHTML = '<span class="text-slate-600 text-xs opacity-0 hover:opacity-100">+ Add</span>';
                return;
            }

            // 2. Save
            const saveRes = await fetch(window.djangoUrls.saveSlot, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify({
                    class_id: state.currentClassId, day: day, period: period,
                    subject_id: this.selectedSubject.id
                })
            });

            if (saveRes.ok) {
                cell.innerHTML = `<span class="text-xs font-bold text-teal-400 bg-teal-900/20 px-2 py-1 rounded block">${this.selectedSubject.code}</span>`;
            }
        } catch (e) { console.error(e); cell.innerHTML = 'Error'; }
    },

    saveConfig() {
        if (!this.config || !this.config.working_days) {
            alert("Timetable configuration not loaded. Refresh.");
            return;
        }
        document.getElementById('tt-set-start').value = this.config.start;
        document.getElementById('tt-set-end').value = this.config.end;
        document.getElementById('tt-set-periods').value = this.config.periods;

        // Render Days Checkboxes
        const daysContainer = document.getElementById('tt-set-days');
        if (daysContainer) {
            daysContainer.innerHTML = '';
            const allDays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
            allDays.forEach(day => {
                const isChecked = this.config.working_days.includes(day);
                const dayEl = document.createElement('label');
                dayEl.className = `px-3 py-1 text-xs font-bold rounded-full cursor-pointer transition select-none ${isChecked ? 'bg-teal-600 text-white' : 'bg-slate-700 text-slate-400 hover:bg-slate-600'}`;
                dayEl.textContent = day.substring(0, 3);
                dayEl.setAttribute('data-day', day);
                dayEl.onclick = (e) => {
                    e.preventDefault();
                    const target = e.currentTarget;
                    if (target.classList.contains('bg-teal-600')) {
                        target.classList.remove('bg-teal-600', 'text-white');
                        target.classList.add('bg-slate-700', 'text-slate-400');
                    } else {
                        target.classList.remove('bg-slate-700', 'text-slate-400');
                        target.classList.add('bg-teal-600', 'text-white');
                    }
                };
                daysContainer.appendChild(dayEl);
            });
        }
        document.getElementById('modal-tt-settings').classList.remove('hidden');
        document.getElementById('modal-tt-settings').classList.add('flex');
    },

    async applySettings() {
        const start_date = document.getElementById('tt-set-start').value;
        const end_date = document.getElementById('tt-set-end').value;
        const periods = document.getElementById('tt-set-periods').value;
        const selectedDays = [];
        document.querySelectorAll('#tt-set-days > label.bg-teal-600').forEach(el => {
            selectedDays.push(el.getAttribute('data-day'));
        });

        if (!start_date || !end_date || selectedDays.length === 0) return alert("Fill configuration.");

        try {
            const res = await fetch(window.djangoUrls.saveTimetableConfig, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                body: JSON.stringify({
                    class_id: state.currentClassId, start_date, end_date, periods, working_days: selectedDays
                })
            });
            if (res.ok) {
                alert("Applied!");
                document.getElementById('modal-tt-settings').classList.add('hidden');
                await this.loadData();
            } else {
                const d = await res.json();
                alert(d.error);
            }
        } catch (e) { alert("Network Error"); }
    },

    adjustHours(index, change) {
        if (this.config && this.config.subjects[index]) {
            let newVal = this.config.subjects[index].weekly_hours_needed + change;
            if (newVal < 1) newVal = 1;
            this.config.subjects[index].weekly_hours_needed = newVal;
            this.renderPalette();
        }
    },
};

// --- ADD SINGLE STUDENT LOGIC (Extend classMgr) ---
classMgr.openAddStudent = function () {
    document.getElementById('modal-add-single-student').classList.remove('hidden');
    document.getElementById('modal-add-single-student').classList.add('flex');
    document.getElementById('new-stu-reg').value = '';
    document.getElementById('new-stu-name').value = '';
    document.getElementById('new-stu-email').value = '';
};

classMgr.addSingleStudent = async function () {
    const reg = document.getElementById('new-stu-reg').value;
    const name = document.getElementById('new-stu-name').value;
    const email = document.getElementById('new-stu-email').value;

    if (!reg || !name) return alert("Fill required fields");

    const res = await fetch(window.djangoUrls.addStudent, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify({
            class_id: state.currentClassId,
            reg_no: reg,
            name: name,
            email: email
        })
    });

    const d = await res.json();
    if (res.ok) {
        alert("Student Added.");
        document.getElementById('modal-add-single-student').classList.add('hidden');
        this.open(state.currentClassId); // Refresh Roster
    } else {
        alert(d.error);
    }
};


// 3. EXPOSE NEW MANAGERS
window.dangerMgr = dangerMgr;
window.facultyMgr = facultyMgr;
// EXPOSE TO WINDOW
window.ui = ui;
window.api = api;
window.modals = modals;
window.resourceMgr = resourceMgr;
window.classMgr = classMgr;
window.adminNotif = adminNotif;
window.analyticsMgr = analyticsMgr;

// INIT
document.addEventListener('DOMContentLoaded', () => {
    // Start the UI
    if (ui && ui.init) ui.init();

    // SAFE Event Listeners (Prevents crashing if button is missing)
    const closeMetricsBtn = document.getElementById('close-metrics-btn');
    if (closeMetricsBtn) {
        closeMetricsBtn.onclick = () => {
            const modal = document.getElementById('metrics-modal');
            if (modal) modal.classList.add('hidden');
        };
    }
});
