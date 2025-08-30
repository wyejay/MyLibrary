
// Global variables
let currentUser = null;
let allFiles = [];
let categories = [];
let currentCategory = 'all';
let currentTheme = localStorage.getItem('theme') || 'light';
let gridSize = localStorage.getItem('gridSize') || 'auto';

// Elements
const authSection = document.getElementById('auth');
const mainNav = document.getElementById('mainNav');
const userInfo = document.getElementById('userInfo');
const fileGrid = document.getElementById('fileGrid');
const searchResults = document.getElementById('searchResults');
const uploadForm = document.getElementById('uploadForm');
const categorySelect = document.getElementById('category');
const progressBar = document.querySelector('.progress-bar');
const progressFill = document.querySelector('.progress-fill');
const settingsModal = document.getElementById('settingsModal');

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
  initializeTheme();
  initializeGridSize();
  checkAuthStatus();
  setupEventListeners();
  checkInviteCode();
});

// Check for invite code in URL
function checkInviteCode() {
  const urlParams = new URLSearchParams(window.location.search);
  const inviteCode = urlParams.get('invite');
  const email = urlParams.get('email');
  
  if (inviteCode && email) {
    document.getElementById('registerEmail').value = email;
    document.getElementById('registerForm').dataset.inviteCode = inviteCode;
    switchAuthTab('register');
    showStatus('Please complete your registration using the invitation.', 'success', 'authStatus');
  }
}

// Theme management
function initializeTheme() {
  document.documentElement.setAttribute('data-theme', currentTheme);
  const themeOptions = document.querySelectorAll('.theme-option');
  themeOptions.forEach(option => {
    option.classList.toggle('selected', option.dataset.theme === currentTheme);
  });
}

function setTheme(theme) {
  currentTheme = theme;
  localStorage.setItem('theme', theme);
  document.documentElement.setAttribute('data-theme', theme);
  
  const themeOptions = document.querySelectorAll('.theme-option');
  themeOptions.forEach(option => {
    option.classList.toggle('selected', option.dataset.theme === theme);
  });
}

// Grid size management
function initializeGridSize() {
  document.getElementById('gridSize').value = gridSize;
  updateGridSize(gridSize);
}

function updateGridSize(size) {
  gridSize = size;
  localStorage.setItem('gridSize', size);
  
  const grids = [fileGrid, searchResults];
  grids.forEach(grid => {
    if (size === 'auto') {
      grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(320px, 1fr))';
    } else {
      grid.style.gridTemplateColumns = `repeat(${size}, 1fr)`;
    }
  });
}

// Settings modal
function openSettings() {
  settingsModal.classList.add('active');
  populateDefaultCategorySelect();
}

function closeSettings() {
  settingsModal.classList.remove('active');
}

function populateDefaultCategorySelect() {
  const defaultCategorySelect = document.getElementById('defaultCategory');
  defaultCategorySelect.innerHTML = '<option value="">No Default</option>';
  categories.forEach(category => {
    const option = document.createElement('option');
    option.value = category;
    option.textContent = category;
    defaultCategorySelect.appendChild(option);
  });
}

function exportData() {
  if (!currentUser) return;
  
  const userData = {
    user: currentUser,
    uploadedFiles: allFiles.filter(f => f.uploaded_by === currentUser.username),
    exportDate: new Date().toISOString()
  };
  
  const blob = new Blob([JSON.stringify(userData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `edulibrary-data-${currentUser.username}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Generate invite link
function generateInviteLink() {
  const baseUrl = window.location.origin;
  const inviteCode = currentUser ? btoa(currentUser.username) : 'general';
  const inviteUrl = `${baseUrl}?invite=${inviteCode}`;
  document.getElementById('inviteLink').textContent = inviteUrl;
}

function copyInviteLink() {
  const inviteLink = document.getElementById('inviteLink').textContent;
  navigator.clipboard.writeText(inviteLink).then(() => {
    showStatus('Invite link copied to clipboard!', 'success', 'inviteStatus');
  }).catch(() => {
    showStatus('Failed to copy link', 'error', 'inviteStatus');
  });
}

// Check if user is logged in
async function checkAuthStatus() {
  try {
    const response = await fetch('/user-info');
    const data = await response.json();
    
    if (data.logged_in) {
      currentUser = data.user;
      showMainApp();
      loadFiles();
      generateInviteLink();
    } else {
      showAuthScreen();
    }
  } catch (error) {
    console.error('Auth check failed:', error);
    showAuthScreen();
  }
}

// Switch between auth tabs
function switchAuthTab(tab) {
  const tabs = document.querySelectorAll('.auth-tab');
  const loginForm = document.getElementById('loginForm');
  const registerForm = document.getElementById('registerForm');
  
  tabs.forEach(t => t.classList.remove('active'));
  document.querySelector(`[onclick="switchAuthTab('${tab}')"]`).classList.add('active');
  
  if (tab === 'login') {
    loginForm.style.display = 'block';
    registerForm.style.display = 'none';
  } else {
    loginForm.style.display = 'none';
    registerForm.style.display = 'block';
  }
}

// Setup event listeners
function setupEventListeners() {
  // Auth forms
  document.getElementById('loginFormElement').addEventListener('submit', handleLogin);
  document.getElementById('registerFormElement').addEventListener('submit', handleRegister);
  
  // Navigation
  document.querySelectorAll('nav button').forEach(button => {
    button.addEventListener('click', () => switchSection(button.dataset.section));
  });
  
  // Upload form
  uploadForm.addEventListener('submit', handleUpload);
  
  // Search
  document.getElementById('searchInput').addEventListener('input', handleSearch);
  
  // Invite form
  document.getElementById('inviteForm').addEventListener('submit', handleInvite);
  
  // Support form
  document.getElementById('supportForm').addEventListener('submit', handleSupportTicket);
  
  // Close modal on backdrop click
  settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) {
      closeSettings();
    }
  });
}

// Handle support ticket submission
async function handleSupportTicket(e) {
  e.preventDefault();
  const title = document.getElementById('supportTitle').value;
  const description = document.getElementById('supportDescription').value;
  const priority = document.getElementById('supportPriority').value;
  
  try {
    const response = await fetch('/support/tickets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, description, priority })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      showStatus('Support ticket submitted successfully!', 'success', 'supportStatus');
      document.getElementById('supportForm').reset();
      loadSupportTickets();
    } else {
      showStatus(data.error || 'Failed to submit ticket', 'error', 'supportStatus');
    }
  } catch (error) {
    showStatus('Failed to submit ticket. Please try again.', 'error', 'supportStatus');
  }
}

// Load support tickets
async function loadSupportTickets() {
  try {
    const response = await fetch('/support/tickets');
    const data = await response.json();
    
    const container = document.getElementById('supportTickets');
    if (data.tickets.length === 0) {
      container.innerHTML = '<p>No support tickets yet.</p>';
      return;
    }
    
    container.innerHTML = data.tickets.map(ticket => `
      <div class="ticket-card">
        <div class="ticket-header">
          <h4>${ticket.title}</h4>
          <div>
            <span class="ticket-status ${ticket.status}">${ticket.status}</span>
            <span class="ticket-priority ${ticket.priority}">${ticket.priority}</span>
          </div>
        </div>
        <p>${ticket.description}</p>
        <div class="ticket-meta">
          Created: ${formatDate(ticket.created_date)}
          ${ticket.resolved_date ? `• Resolved: ${formatDate(ticket.resolved_date)}` : ''}
        </div>
        ${ticket.admin_response ? `
          <div style="margin-top: 1rem; padding: 1rem; background: var(--surface-elevated); border-radius: 8px;">
            <strong>Admin Response:</strong><br>
            ${ticket.admin_response}
          </div>
        ` : ''}
      </div>
    `).join('');
  } catch (error) {
    console.error('Failed to load support tickets:', error);
  }
}

// Handle invite
async function handleInvite(e) {
  e.preventDefault();
  const email = document.getElementById('inviteEmail').value;
  const message = document.getElementById('inviteMessage').value;
  
  try {
    const response = await fetch('/send-invite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, message })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      showStatus('Invitation sent successfully!', 'success', 'inviteStatus');
      document.getElementById('inviteForm').reset();
    } else {
      showStatus(data.error || 'Failed to send invitation', 'error', 'inviteStatus');
    }
  } catch (error) {
    showStatus('Failed to send invitation. Please try again.', 'error', 'inviteStatus');
  }
}

// Handle login
async function handleLogin(e) {
  e.preventDefault();
  const username = document.getElementById('loginUsername').value;
  const password = document.getElementById('loginPassword').value;
  
  try {
    const response = await fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      currentUser = data.user;
      showStatus('Login successful!', 'success', 'authStatus');
      setTimeout(() => {
        showMainApp();
        loadFiles();
        generateInviteLink();
      }, 1000);
    } else {
      showStatus(data.error, 'error', 'authStatus');
    }
  } catch (error) {
    showStatus('Login failed. Please try again.', 'error', 'authStatus');
  }
}

// Handle registration
async function handleRegister(e) {
  e.preventDefault();
  const username = document.getElementById('registerUsername').value;
  const email = document.getElementById('registerEmail').value;
  const password = document.getElementById('registerPassword').value;
  const inviteCode = document.getElementById('registerForm').dataset.inviteCode || '';
  
  try {
    const response = await fetch('/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, email, password, invite_code: inviteCode })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      showStatus('Registration successful! Please login.', 'success', 'authStatus');
      switchAuthTab('login');
    } else {
      showStatus(data.error, 'error', 'authStatus');
    }
  } catch (error) {
    showStatus('Registration failed. Please try again.', 'error', 'authStatus');
  }
}

// Show main app
function showMainApp() {
  authSection.style.display = 'none';
  mainNav.style.display = 'flex';
  
  // Show admin nav if user is admin
  const adminNavBtn = document.getElementById('adminNavBtn');
  if (currentUser.is_admin) {
    adminNavBtn.style.display = 'block';
  }
  
  // Update user info
  userInfo.innerHTML = `
    <button class="settings-btn" onclick="openSettings()" title="Settings">
      ⚙️
    </button>
    <div class="user-stats">
      📤 ${currentUser.uploads_count} uploads • 📥 ${currentUser.downloads_count} downloads
      ${currentUser.is_admin ? ' • 👑 Admin' : ''}
    </div>
    <span>Welcome, ${currentUser.username}!</span>
    <button class="btn btn-secondary" onclick="logout()">Logout</button>
  `;
  
  // Show browse section by default
  switchSection('browse');
}

// Show auth screen
function showAuthScreen() {
  authSection.style.display = 'block';
  mainNav.style.display = 'none';
  document.querySelectorAll('main section:not(#auth)').forEach(s => s.style.display = 'none');
}

// Logout
async function logout() {
  try {
    await fetch('/logout', { method: 'POST' });
    currentUser = null;
    showAuthScreen();
  } catch (error) {
    console.error('Logout failed:', error);
  }
}

// Switch sections
function switchSection(sectionName) {
  document.querySelectorAll('nav button').forEach(btn => btn.classList.remove('active'));
  document.querySelector(`[data-section="${sectionName}"]`).classList.add('active');
  
  document.querySelectorAll('main section:not(#auth)').forEach(sec => {
    sec.classList.remove('active');
    sec.style.display = 'none';
  });
  
  document.getElementById(sectionName).style.display = 'block';
  document.getElementById(sectionName).classList.add('active');
  
  if (sectionName === 'browse') {
    loadFiles();
  } else if (sectionName === 'support') {
    loadSupportTickets();
  } else if (sectionName === 'admin' && currentUser.is_admin) {
    loadAdminData();
  }
}

// Load files
async function loadFiles() {
  try {
    const response = await fetch('/files');
    const data = await response.json();
    allFiles = data.files || [];
    categories = data.categories || [];
    
    updateCategoryFilters();
    populateCategorySelect();
    renderFiles();
  } catch (error) {
    console.error('Failed to load files:', error);
  }
}

// Update category filters
function updateCategoryFilters() {
  const filterContainer = document.querySelector('.category-filter');
  const existingButtons = filterContainer.querySelectorAll('.category-btn:not([data-category="all"])');
  existingButtons.forEach(btn => btn.remove());
  
  categories.forEach(category => {
    const btn = document.createElement('button');
    btn.className = 'category-btn';
    btn.dataset.category = category;
    btn.textContent = category;
    btn.onclick = () => filterByCategory(category);
    filterContainer.appendChild(btn);
  });
}

// Populate category select
function populateCategorySelect() {
  categorySelect.innerHTML = '<option value="">Select a category</option>';
  categories.forEach(category => {
    const option = document.createElement('option');
    option.value = category;
    option.textContent = category;
    categorySelect.appendChild(option);
  });
}

// Filter by category
function filterByCategory(category) {
  currentCategory = category;
  document.querySelectorAll('.category-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelector(`[data-category="${category}"]`).classList.add('active');
  renderFiles();
}

// Render files
function renderFiles(filesToRender = null) {
  const container = filesToRender ? searchResults : fileGrid;
  const files = filesToRender || (currentCategory === 'all' ? allFiles : allFiles.filter(f => f.category === currentCategory));
  
  container.innerHTML = '';
  
  if (files.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="icon">📁</div>
        <h3>No files found</h3>
        <p>${filesToRender ? 'Try a different search term' : 'Upload some PDFs to get started!'}</p>
      </div>
    `;
    return;
  }
  
  files.forEach(file => {
    const card = createFileCard(file);
    container.appendChild(card);
  });
}

// Create file card
function createFileCard(file) {
  const card = document.createElement('div');
  card.className = 'file-card';
  
  card.innerHTML = `
    <div class="file-header">
      <div class="file-icon">PDF</div>
      <div class="file-info">
        <h3 title="${file.filename}">
          ${file.original_name}
          ${file.is_featured ? '<span class="featured-badge">⭐ Featured</span>' : ''}
        </h3>
        <div class="file-meta">
          ${file.size_mb}MB • ${formatDate(file.upload_date)}<br>
          👤 ${file.uploaded_by} • 📥 ${file.download_count} downloads
        </div>
        <span class="file-category">${file.category}</span>
      </div>
    </div>
    ${file.description ? `<div class="file-description">${file.description}</div>` : ''}
    ${file.tags && file.tags.length ? `<div class="file-tags">${file.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}</div>` : ''}
    <div class="file-actions">
      <button class="btn btn-warning" onclick="previewFile(${file.id})">Preview</button>
      <button class="btn" onclick="downloadFile(${file.id})">Download</button>
      ${file.uploaded_by === currentUser.username || currentUser.is_admin ? 
        `<button class="btn btn-danger" onclick="deleteFile(${file.id})">Delete</button>` : ''}
    </div>
  `;
  
  return card;
}

// Handle upload
async function handleUpload(e) {
  e.preventDefault();
  const files = document.getElementById('pdfFile').files;
  const category = categorySelect.value;
  const description = document.getElementById('description').value;
  const tags = document.getElementById('tags') ? document.getElementById('tags').value : '';
  
  if (!files.length || !category) {
    showStatus('Please select file(s) and category.', 'error', 'uploadStatus');
    return;
  }
  
  uploadForm.classList.add('loading');
  progressBar.style.display = 'block';
  
  try {
    let successCount = 0;
    let errorCount = 0;
    
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const formData = new FormData();
      formData.append('pdf', file);
      formData.append('category', category);
      formData.append('description', description);
      formData.append('tags', tags);
      
      const progress = ((i + 1) / files.length) * 100;
      progressFill.style.width = `${progress}%`;
      
      try {
        const response = await fetch('/upload', {
          method: 'POST',
          body: formData
        });
        
        if (response.ok) {
          successCount++;
        } else {
          errorCount++;
        }
      } catch (error) {
        errorCount++;
      }
    }
    
    if (successCount > 0) {
      showStatus(`Successfully uploaded ${successCount} file(s).`, 'success', 'uploadStatus');
      uploadForm.reset();
      loadFiles();
      // Update user stats
      currentUser.uploads_count += successCount;
    } else {
      showStatus('All uploads failed. Please try again.', 'error', 'uploadStatus');
    }
    
  } catch (error) {
    showStatus('Upload failed. Please try again.', 'error', 'uploadStatus');
  } finally {
    uploadForm.classList.remove('loading');
    progressBar.style.display = 'none';
    progressFill.style.width = '0%';
  }
}

// Handle search
function handleSearch(e) {
  const query = e.target.value.trim().toLowerCase();
  
  if (!query) {
    searchResults.innerHTML = `
      <div class="empty-state">
        <div class="icon">🔍</div>
        <h3>Search PDFs</h3>
        <p>Enter keywords to search through the library</p>
      </div>
    `;
    return;
  }
  
  const filtered = allFiles.filter(file => 
    file.original_name.toLowerCase().includes(query) ||
    file.category.toLowerCase().includes(query) ||
    file.description.toLowerCase().includes(query) ||
    file.uploaded_by.toLowerCase().includes(query) ||
    (file.tags && file.tags.some(tag => tag.toLowerCase().includes(query)))
  );
  
  renderFiles(filtered);
}

// File actions
function previewFile(fileId) {
  window.open(`/preview/${fileId}`, '_blank');
}

async function downloadFile(fileId) {
  try {
    const link = document.createElement('a');
    link.href = `/download/${fileId}`;
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    // Update download count and user stats
    currentUser.downloads_count++;
    setTimeout(loadFiles, 1000);
  } catch (error) {
    alert('Download failed. Please make sure you are logged in.');
  }
}

async function deleteFile(fileId) {
  const file = allFiles.find(f => f.id === fileId);
  if (!confirm(`Are you sure you want to delete "${file.original_name}"?`)) {
    return;
  }
  
  try {
    const response = await fetch(`/delete/${fileId}`, {
      method: 'DELETE'
    });
    
    if (response.ok) {
      loadFiles();
      if (file.uploaded_by === currentUser.username) {
        currentUser.uploads_count = Math.max(0, currentUser.uploads_count - 1);
      }
    } else {
      const data = await response.json();
      alert(data.error || 'Failed to delete file.');
    }
  } catch (error) {
    alert('Failed to delete file.');
  }
}

// Admin functions
function switchAdminTab(tab) {
  document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`[onclick="switchAdminTab('${tab}')"]`).classList.add('active');
  
  document.querySelectorAll('.admin-content').forEach(content => {
    content.style.display = 'none';
  });
  
  document.getElementById(`admin${tab.charAt(0).toUpperCase() + tab.slice(1)}`).style.display = 'block';
  
  if (tab === 'users') loadAdminUsers();
  else if (tab === 'files') loadAdminFiles();
  else if (tab === 'support') loadAdminSupport();
  else if (tab === 'analytics') loadAnalytics();
}

async function loadAdminData() {
  loadAdminUsers();
}

async function loadAdminUsers() {
  try {
    const response = await fetch('/admin/users');
    const data = await response.json();
    
    const container = document.getElementById('usersList');
    container.innerHTML = data.users.map(user => `
      <div class="user-card">
        <div class="user-info">
          <h4>${user.username} ${user.is_admin ? '👑' : ''} ${!user.is_active ? '🚫' : ''}</h4>
          <div class="user-meta">
            ${user.email} • Joined: ${formatDate(user.join_date)}<br>
            Uploads: ${user.uploads_count} • Downloads: ${user.downloads_count}<br>
            Status: ${user.is_active ? 'Active' : 'Inactive'}
          </div>
        </div>
        <div class="user-actions">
          ${!user.is_admin ? `
            <button class="btn ${user.is_active ? 'btn-warning' : 'btn-secondary'}" 
                    onclick="toggleUserStatus(${user.id})">
              ${user.is_active ? 'Deactivate' : 'Activate'}
            </button>
            <button class="btn btn-danger" onclick="deleteUser(${user.id})">Delete</button>
          ` : '<span>Admin User</span>'}
        </div>
      </div>
    `).join('');
  } catch (error) {
    console.error('Failed to load users:', error);
  }
}

async function deleteUser(userId) {
  if (!confirm('Are you sure you want to delete this user? This will also delete all their files.')) {
    return;
  }
  
  try {
    const response = await fetch(`/admin/users/${userId}/delete`, {
      method: 'DELETE'
    });
    
    if (response.ok) {
      loadAdminUsers();
      showStatus('User deleted successfully', 'success', 'adminStatus');
    } else {
      const data = await response.json();
      showStatus(data.error || 'Failed to delete user', 'error', 'adminStatus');
    }
  } catch (error) {
    showStatus('Failed to delete user', 'error', 'adminStatus');
  }
}

async function createBackup() {
  try {
    const response = await fetch('/admin/backup', {
      method: 'POST'
    });
    
    const data = await response.json();
    
    if (response.ok) {
      showStatus(data.message, 'success', 'adminStatus');
    } else {
      showStatus(data.error || 'Backup failed', 'error', 'adminStatus');
    }
  } catch (error) {
    showStatus('Backup failed', 'error', 'adminStatus');
  }
}

async function toggleUserStatus(userId) {
  try {
    const response = await fetch(`/admin/users/${userId}/toggle-status`, {
      method: 'POST'
    });
    
    if (response.ok) {
      loadAdminUsers();
    } else {
      const data = await response.json();
      alert(data.error || 'Failed to update user status');
    }
  } catch (error) {
    alert('Failed to update user status');
  }
}

async function loadAdminFiles() {
  try {
    const response = await fetch('/files');
    const data = await response.json();
    
    const container = document.getElementById('adminFilesList');
    container.innerHTML = data.files.map(file => `
      <div class="admin-file-card">
        <div class="file-info">
          <h4>${file.original_name} ${file.is_featured ? '⭐' : ''}</h4>
          <div class="file-meta">
            ${file.category} • ${file.size_mb}MB • ${file.download_count} downloads<br>
            Uploaded by: ${file.uploaded_by}
          </div>
        </div>
        <div class="file-actions">
          <button class="btn ${file.is_featured ? 'btn-warning' : 'btn-secondary'}" 
                  onclick="toggleFeatured(${file.id})">
            ${file.is_featured ? 'Unfeature' : 'Feature'}
          </button>
          <button class="btn btn-danger" onclick="deleteFile(${file.id})">Delete</button>
        </div>
      </div>
    `).join('');
  } catch (error) {
    console.error('Failed to load files:', error);
  }
}

async function toggleFeatured(fileId) {
  try {
    const response = await fetch(`/admin/files/featured/${fileId}`, {
      method: 'POST'
    });
    
    if (response.ok) {
      loadAdminFiles();
      loadFiles(); // Refresh main file list
    } else {
      const data = await response.json();
      alert(data.error || 'Failed to update file status');
    }
  } catch (error) {
    alert('Failed to update file status');
  }
}

async function loadAdminSupport() {
  try {
    const response = await fetch('/support/tickets');
    const data = await response.json();
    
    const container = document.getElementById('adminTicketsList');
    container.innerHTML = data.tickets.map(ticket => `
      <div class="ticket-card">
        <div class="ticket-header">
          <h4>${ticket.title}</h4>
          <div>
            <span class="ticket-status ${ticket.status}">${ticket.status}</span>
            <span class="ticket-priority ${ticket.priority}">${ticket.priority}</span>
          </div>
        </div>
        <p><strong>User:</strong> ${ticket.user}</p>
        <p>${ticket.description}</p>
        <div class="ticket-meta">
          Created: ${formatDate(ticket.created_date)}
        </div>
        ${ticket.status !== 'resolved' ? `
          <div style="margin-top: 1rem;">
            <textarea id="response-${ticket.id}" placeholder="Admin response..." rows="3" style="width: 100%; margin-bottom: 0.5rem;"></textarea>
            <div style="display: flex; gap: 8px;">
              <button class="btn btn-secondary" onclick="respondToTicket(${ticket.id}, 'in-progress')">Mark In Progress</button>
              <button class="btn" onclick="respondToTicket(${ticket.id}, 'resolved')">Resolve</button>
            </div>
          </div>
        ` : ''}
        ${ticket.admin_response ? `
          <div style="margin-top: 1rem; padding: 1rem; background: var(--surface-elevated); border-radius: 8px;">
            <strong>Admin Response:</strong><br>
            ${ticket.admin_response}
          </div>
        ` : ''}
      </div>
    `).join('');
  } catch (error) {
    console.error('Failed to load tickets:', error);
  }
}

async function respondToTicket(ticketId, status) {
  const response = document.getElementById(`response-${ticketId}`).value.trim();
  
  if (!response) {
    alert('Please enter a response');
    return;
  }
  
  try {
    const res = await fetch(`/admin/tickets/${ticketId}/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ response, status })
    });
    
    if (res.ok) {
      loadAdminSupport();
    } else {
      const data = await res.json();
      alert(data.error || 'Failed to respond to ticket');
    }
  } catch (error) {
    alert('Failed to respond to ticket');
  }
}

async function loadAnalytics() {
  try {
    const response = await fetch('/analytics');
    const data = await response.json();
    
    const container = document.getElementById('analyticsData');
    container.innerHTML = `
      <div class="analytics-grid">
        <div class="stat-card">
          <div class="stat-number">${data.stats.total_users}</div>
          <div class="stat-label">Total Users</div>
        </div>
        <div class="stat-card">
          <div class="stat-number">${data.stats.active_users}</div>
          <div class="stat-label">Active Users</div>
        </div>
        <div class="stat-card">
          <div class="stat-number">${data.stats.total_files}</div>
          <div class="stat-label">Total Files</div>
        </div>
        <div class="stat-card">
          <div class="stat-number">${data.stats.total_downloads}</div>
          <div class="stat-label">Total Downloads</div>
        </div>
        <div class="stat-card">
          <div class="stat-number">${data.stats.total_size_mb} MB</div>
          <div class="stat-label">Storage Used</div>
        </div>
        <div class="stat-card">
          <div class="stat-number">${data.stats.open_tickets}</div>
          <div class="stat-label">Open Tickets</div>
        </div>
      </div>
      
      <h3>📊 Category Distribution</h3>
      <div class="category-stats" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 1rem 0;">
        ${data.categories.map(cat => `
          <div class="stat-item" style="background: var(--surface-elevated); padding: 1rem; border-radius: 8px; border: 1px solid var(--border);">
            <strong>${cat.category}</strong><br>
            ${cat.count} files
          </div>
        `).join('')}
      </div>
      
      <h3>📁 Recent Uploads</h3>
      <div class="recent-uploads" style="max-height: 300px; overflow-y: auto;">
        ${data.recent_uploads.map(file => `
          <div class="upload-item" style="background: var(--surface-elevated); padding: 0.75rem; margin: 0.5rem 0; border-radius: 8px; border: 1px solid var(--border);">
            <strong>${file.original_name}</strong><br>
            <small>📤 ${file.uploaded_by} • ${formatDate(file.upload_date)} • ${file.download_count} downloads</small>
          </div>
        `).join('')}
      </div>
    `;
  } catch (error) {
    console.error('Failed to load analytics:', error);
    container.innerHTML = '<p>Failed to load analytics data.</p>';
  }
}

// Utility functions
function formatDate(isoString) {
  if (!isoString || isoString === 'Unknown') return 'Unknown';
  const date = new Date(isoString);
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
}

function showStatus(message, type, containerId) {
  const container = document.getElementById(containerId);
  container.innerHTML = `<div class="status-message status-${type}">${message}</div>`;
  setTimeout(() => {
    container.innerHTML = '';
  }, 5000);
}

// Initialize category filter
document.addEventListener('DOMContentLoaded', function() {
  const allCategoryBtn = document.querySelector('[data-category="all"]');
  if (allCategoryBtn) {
    allCategoryBtn.onclick = () => filterByCategory('all');
  }
});
// Global state
let currentUser = null;
let currentSection = 'browse';
let currentAdminTab = 'analytics';

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    checkAuthStatus();
    loadCategories();
    setupEventListeners();
});

function setupEventListeners() {
    // Auth forms
    document.getElementById('login-form').addEventListener('submit', handleLogin);
    document.getElementById('register-form').addEventListener('submit', handleRegister);
    document.getElementById('upload-form').addEventListener('submit', handleUpload);
    document.getElementById('invite-form').addEventListener('submit', handleInvite);
    document.getElementById('support-form').addEventListener('submit', handleSupportTicket);
    
    // Search functionality
    document.getElementById('search-input').addEventListener('input', debounce(loadFiles, 300));
    document.getElementById('category-filter').addEventListener('change', loadFiles);
    document.getElementById('featured-only').addEventListener('change', loadFiles);
}

// Authentication functions
async function checkAuthStatus() {
    try {
        const response = await fetch('/user-info');
        const data = await response.json();
        
        if (data.logged_in) {
            currentUser = data.user;
            showApp();
            updateUserStats();
            loadFiles();
            loadUserTickets();
            if (currentUser.is_admin) {
                showAdminAccess();
                loadAnalytics();
            }
        } else {
            showAuth();
        }
    } catch (error) {
        console.error('Auth check failed:', error);
        showAuth();
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    
    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, password})
        });
        
        const data = await response.json();
        if (response.ok) {
            currentUser = data.user;
            showApp();
            updateUserStats();
            loadFiles();
            if (currentUser.is_admin) {
                showAdminAccess();
            }
            showNotification('Login successful!', 'success');
        } else {
            showNotification(data.error, 'error');
        }
    } catch (error) {
        showNotification('Login failed', 'error');
    }
}

async function handleRegister(e) {
    e.preventDefault();
    const username = document.getElementById('register-username').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    const invite_code = document.getElementById('invite-code').value;
    
    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, email, password, invite_code})
        });
        
        const data = await response.json();
        if (response.ok) {
            showNotification('Registration successful! Please login.', 'success');
            switchAuthTab('login');
        } else {
            showNotification(data.error, 'error');
        }
    } catch (error) {
        showNotification('Registration failed', 'error');
    }
}

async function logout() {
    try {
        await fetch('/logout', {method: 'POST'});
        currentUser = null;
        session.clear();
        showAuth();
        showNotification('Logged out successfully', 'success');
    } catch (error) {
        showNotification('Logout failed', 'error');
    }
}

// UI Functions
function showAuth() {
    document.getElementById('auth-container').classList.remove('hidden');
    document.getElementById('app-container').classList.add('hidden');
}

function showApp() {
    document.getElementById('auth-container').classList.add('hidden');
    document.getElementById('app-container').classList.remove('hidden');
}

function switchAuthTab(tab) {
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.auth-form').forEach(f => f.classList.add('hidden'));
    
    if (tab === 'login') {
        document.querySelector('.auth-tab').classList.add('active');
        document.getElementById('login-form').classList.remove('hidden');
    } else {
        document.querySelectorAll('.auth-tab')[1].classList.add('active');
        document.getElementById('register-form').classList.remove('hidden');
    }
}

function showSection(section) {
    currentSection = section;
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.section').forEach(sec => sec.classList.remove('active'));
    
    event.target.classList.add('active');
    document.getElementById(`${section}-section`).classList.add('active');
    
    if (section === 'browse') {
        loadFiles();
    } else if (section === 'admin' && currentUser.is_admin) {
        loadAnalytics();
    } else if (section === 'support') {
        loadUserTickets();
    }
}

function showAdminAccess() {
    document.getElementById('admin-nav').classList.remove('hidden');
}

function updateUserStats() {
    if (currentUser) {
        document.getElementById('user-stats').textContent = 
            `${currentUser.username} • ${currentUser.uploads_count} uploads • ${currentUser.downloads_count} downloads`;
    }
}

// File management
async function loadFiles() {
    try {
        const category = document.getElementById('category-filter').value;
        const search = document.getElementById('search-input').value;
        const featured = document.getElementById('featured-only').checked;
        
        const params = new URLSearchParams({
            category: category,
            search: search,
            featured: featured
        });
        
        const response = await fetch(`/files?${params}`);
        const data = await response.json();
        
        displayFiles(data.files);
    } catch (error) {
        console.error('Failed to load files:', error);
    }
}

function displayFiles(files) {
    const container = document.getElementById('files-container');
    container.innerHTML = '';
    
    if (files.length === 0) {
        container.innerHTML = '<div class="text-center text-muted">No files found</div>';
        return;
    }
    
    files.forEach(file => {
        const fileCard = document.createElement('div');
        fileCard.className = 'file-card';
        fileCard.innerHTML = `
            <div class="file-header">
                <div>
                    <h3 class="file-title">${file.original_name}</h3>
                    <div class="file-meta">
                        📂 ${file.category} • 📁 ${file.size_mb}MB • 👤 ${file.uploaded_by}
                        <br>📅 ${new Date(file.upload_date).toLocaleDateString()}
                        • 📥 ${file.download_count} downloads
                    </div>
                </div>
                ${file.is_featured ? '<span class="featured-badge">⭐ Featured</span>' : ''}
            </div>
            
            ${file.description ? `<p class="text-muted mb-2">${file.description}</p>` : ''}
            
            ${file.tags.length > 0 ? `
                <div class="mb-2">
                    ${file.tags.map(tag => `<span class="category-badge">${tag}</span>`).join(' ')}
                </div>
            ` : ''}
            
            <div class="file-actions">
                <button class="btn btn-primary btn-sm" onclick="downloadFile(${file.id})">📥 Download</button>
                <button class="btn btn-secondary btn-sm" onclick="previewFile(${file.id})">👀 Preview</button>
                ${(currentUser.is_admin || file.uploader_id === currentUser.id) ? 
                    `<button class="btn btn-danger btn-sm" onclick="deleteFile(${file.id})">🗑️ Delete</button>` : ''}
            </div>
        `;
        container.appendChild(fileCard);
    });
}

async function handleUpload(e) {
    e.preventDefault();
    const formData = new FormData();
    
    const file = document.getElementById('pdf-file').files[0];
    const category = document.getElementById('upload-category').value;
    const description = document.getElementById('upload-description').value;
    const tags = document.getElementById('upload-tags').value;
    
    if (!file) {
        showNotification('Please select a file', 'error');
        return;
    }
    
    formData.append('pdf', file);
    formData.append('category', category);
    formData.append('description', description);
    formData.append('tags', tags);
    
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        if (response.ok) {
            showNotification('File uploaded successfully!', 'success');
            document.getElementById('upload-form').reset();
            updateUserStats();
            if (currentSection === 'browse') {
                loadFiles();
            }
        } else {
            showNotification(data.error, 'error');
        }
    } catch (error) {
        showNotification('Upload failed', 'error');
    }
}

async function downloadFile(fileId) {
    try {
        window.open(`/download/${fileId}`, '_blank');
        setTimeout(() => {
            updateUserStats();
            loadFiles();
        }, 1000);
    } catch (error) {
        showNotification('Download failed', 'error');
    }
}

function previewFile(fileId) {
    window.open(`/preview/${fileId}`, '_blank');
}

async function deleteFile(fileId) {
    if (!confirm('Are you sure you want to delete this file?')) return;
    
    try {
        const response = await fetch(`/delete/${fileId}`, {method: 'DELETE'});
        const data = await response.json();
        
        if (response.ok) {
            showNotification('File deleted successfully', 'success');
            loadFiles();
            updateUserStats();
        } else {
            showNotification(data.error, 'error');
        }
    } catch (error) {
        showNotification('Delete failed', 'error');
    }
}

// Invitation system
async function handleInvite(e) {
    e.preventDefault();
    const email = document.getElementById('invite-email').value;
    const message = document.getElementById('invite-message').value;
    
    try {
        const response = await fetch('/send-invite', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email, message})
        });
        
        const data = await response.json();
        if (response.ok) {
            showNotification('Invitation sent successfully!', 'success');
            document.getElementById('invite-form').reset();
        } else {
            showNotification(data.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to send invitation', 'error');
    }
}

// Support system
async function handleSupportTicket(e) {
    e.preventDefault();
    const title = document.getElementById('ticket-title').value;
    const priority = document.getElementById('ticket-priority').value;
    const description = document.getElementById('ticket-description').value;
    
    try {
        const response = await fetch('/support/tickets', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title, priority, description})
        });
        
        const data = await response.json();
        if (response.ok) {
            showNotification('Support ticket created successfully!', 'success');
            document.getElementById('support-form').reset();
            loadUserTickets();
        } else {
            showNotification(data.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to create ticket', 'error');
    }
}

async function loadUserTickets() {
    try {
        const response = await fetch('/support/tickets');
        const data = await response.json();
        
        const container = document.getElementById('tickets-container');
        container.innerHTML = '';
        
        if (data.tickets.length === 0) {
            container.innerHTML = '<div class="text-center text-muted">No support tickets yet</div>';
            return;
        }
        
        data.tickets.forEach(ticket => {
            const ticketCard = document.createElement('div');
            ticketCard.className = 'ticket-card';
            ticketCard.innerHTML = `
                <div class="ticket-header">
                    <h4 class="ticket-title">${ticket.title}</h4>
                    <div>
                        <span class="priority-badge priority-${ticket.priority}">${ticket.priority}</span>
                        <span class="status-badge status-${ticket.status}">${ticket.status}</span>
                    </div>
                </div>
                <p class="text-muted mb-2">${ticket.description}</p>
                <div class="text-muted">
                    Created: ${new Date(ticket.created_date).toLocaleDateString()}
                    ${ticket.resolved_date ? ` • Resolved: ${new Date(ticket.resolved_date).toLocaleDateString()}` : ''}
                </div>
                ${ticket.admin_response ? `<div class="mt-2"><strong>Admin Response:</strong> ${ticket.admin_response}</div>` : ''}
            `;
            container.appendChild(ticketCard);
        });
    } catch (error) {
        console.error('Failed to load tickets:', error);
    }
}

// Admin functions
function showAdminTab(tab) {
    currentAdminTab = tab;
    document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.admin-content').forEach(c => c.classList.add('hidden'));
    
    event.target.classList.add('active');
    document.getElementById(`admin-${tab}`).classList.remove('hidden');
    
    switch(tab) {
        case 'analytics': loadAnalytics(); break;
        case 'users': loadAdminUsers(); break;
        case 'files': loadAdminFiles(); break;
        case 'tickets': loadAdminTickets(); break;
    }
}

async function loadAnalytics() {
    if (!currentUser.is_admin) return;
    
    try {
        const response = await fetch('/analytics');
        const data = await response.json();
        
        const container = document.getElementById('analytics-container');
        container.innerHTML = `
            <div class="stat-card">
                <div class="stat-number">${data.stats.total_users}</div>
                <div class="stat-label">Total Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${data.stats.active_users}</div>
                <div class="stat-label">Active Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${data.stats.total_files}</div>
                <div class="stat-label">Total Files</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${data.stats.total_downloads}</div>
                <div class="stat-label">Downloads</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${data.stats.total_size_mb}</div>
                <div class="stat-label">Total Size (MB)</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${data.stats.open_tickets}</div>
                <div class="stat-label">Open Tickets</div>
            </div>
        `;
    } catch (error) {
        console.error('Failed to load analytics:', error);
    }
}

async function loadAdminUsers() {
    if (!currentUser.is_admin) return;
    
    try {
        const response = await fetch('/admin/users');
        const data = await response.json();
        
        const container = document.getElementById('users-container');
        container.innerHTML = '';
        
        data.users.forEach(user => {
            const userCard = document.createElement('div');
            userCard.className = 'user-card';
            userCard.innerHTML = `
                <div class="user-info">
                    <h4>${user.username} ${user.is_admin ? '👑' : ''}</h4>
                    <div class="user-meta">
                        📧 ${user.email} • 📅 ${new Date(user.join_date).toLocaleDateString()}
                        • 📤 ${user.uploads_count} uploads • 📥 ${user.downloads_count} downloads
                        • Status: ${user.is_active ? '✅ Active' : '❌ Inactive'}
                    </div>
                </div>
                <div class="user-actions">
                    ${!user.is_admin ? `
                        <button class="btn btn-sm ${user.is_active ? 'btn-warning' : 'btn-success'}" 
                                onclick="toggleUserStatus(${user.id})">
                            ${user.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="deleteUser(${user.id})">Delete</button>
                    ` : ''}
                </div>
            `;
            container.appendChild(userCard);
        });
    } catch (error) {
        console.error('Failed to load users:', error);
    }
}

async function loadAdminFiles() {
    if (!currentUser.is_admin) return;
    
    try {
        const response = await fetch('/files');
        const data = await response.json();
        
        const container = document.getElementById('admin-files-container');
        container.innerHTML = '';
        
        data.files.forEach(file => {
            const fileCard = document.createElement('div');
            fileCard.className = 'admin-file-card';
            fileCard.innerHTML = `
                <div>
                    <h4>${file.original_name} ${file.is_featured ? '⭐' : ''}</h4>
                    <div class="user-meta">
                        📂 ${file.category} • 📁 ${file.size_mb}MB • 👤 ${file.uploaded_by}
                        • 📥 ${file.download_count} downloads
                    </div>
                </div>
                <div class="user-actions">
                    <button class="btn btn-sm btn-warning" onclick="toggleFeatured(${file.id})">
                        ${file.is_featured ? 'Unfeature' : 'Feature'}
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="deleteFile(${file.id})">Delete</button>
                </div>
            `;
            container.appendChild(fileCard);
        });
    } catch (error) {
        console.error('Failed to load admin files:', error);
    }
}

async function loadAdminTickets() {
    if (!currentUser.is_admin) return;
    
    try {
        const response = await fetch('/support/tickets');
        const data = await response.json();
        
        const container = document.getElementById('admin-tickets-container');
        container.innerHTML = '';
        
        data.tickets.forEach(ticket => {
            const ticketCard = document.createElement('div');
            ticketCard.className = 'ticket-card';
            ticketCard.innerHTML = `
                <div class="ticket-header">
                    <h4 class="ticket-title">${ticket.title}</h4>
                    <div>
                        <span class="priority-badge priority-${ticket.priority}">${ticket.priority}</span>
                        <span class="status-badge status-${ticket.status}">${ticket.status}</span>
                    </div>
                </div>
                <p class="text-muted mb-2">👤 ${ticket.user} • 📅 ${new Date(ticket.created_date).toLocaleDateString()}</p>
                <p class="mb-2">${ticket.description}</p>
                ${ticket.admin_response ? `<div class="mb-2"><strong>Response:</strong> ${ticket.admin_response}</div>` : ''}
                ${ticket.status !== 'resolved' ? `
                    <div class="mt-2">
                        <textarea id="response-${ticket.id}" class="form-control mb-1" placeholder="Enter response..."></textarea>
                        <div class="file-actions">
                            <button class="btn btn-sm btn-success" onclick="respondToTicket(${ticket.id}, 'resolved')">Resolve</button>
                            <button class="btn btn-sm btn-warning" onclick="respondToTicket(${ticket.id}, 'in-progress')">In Progress</button>
                        </div>
                    </div>
                ` : ''}
            `;
            container.appendChild(ticketCard);
        });
    } catch (error) {
        console.error('Failed to load admin tickets:', error);
    }
}

// Admin actions
async function toggleUserStatus(userId) {
    try {
        const response = await fetch(`/admin/users/${userId}/toggle-status`, {method: 'POST'});
        const data = await response.json();
        
        if (response.ok) {
            showNotification(data.message, 'success');
            loadAdminUsers();
        } else {
            showNotification(data.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to update user status', 'error');
    }
}

async function deleteUser(userId) {
    if (!confirm('Are you sure you want to delete this user? This will also delete all their files.')) return;
    
    try {
        const response = await fetch(`/admin/users/${userId}/delete`, {method: 'DELETE'});
        const data = await response.json();
        
        if (response.ok) {
            showNotification('User deleted successfully', 'success');
            loadAdminUsers();
        } else {
            showNotification(data.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to delete user', 'error');
    }
}

async function toggleFeatured(fileId) {
    try {
        const response = await fetch(`/admin/files/featured/${fileId}`, {method: 'POST'});
        const data = await response.json();
        
        if (response.ok) {
            showNotification(data.message, 'success');
            loadAdminFiles();
            if (currentSection === 'browse') {
                loadFiles();
            }
        } else {
            showNotification(data.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to update file', 'error');
    }
}

async function respondToTicket(ticketId, status) {
    const response = document.getElementById(`response-${ticketId}`).value;
    
    if (!response.trim()) {
        showNotification('Please enter a response', 'error');
        return;
    }
    
    try {
        const apiResponse = await fetch(`/admin/tickets/${ticketId}/respond`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({response, status})
        });
        
        const data = await apiResponse.json();
        if (apiResponse.ok) {
            showNotification('Response sent successfully', 'success');
            loadAdminTickets();
        } else {
            showNotification(data.error, 'error');
        }
    } catch (error) {
        showNotification('Failed to send response', 'error');
    }
}

async function createBackup() {
    try {
        const response = await fetch('/admin/backup', {method: 'POST'});
        const data = await response.json();
        
        if (response.ok) {
            showNotification(data.message, 'success');
        } else {
            showNotification(data.error, 'error');
        }
    } catch (error) {
        showNotification('Backup failed', 'error');
    }
}

// Utility functions
async function loadCategories() {
    try {
        const response = await fetch('/files');
        const data = await response.json();
        
        const categorySelect = document.getElementById('category-filter');
        const uploadCategorySelect = document.getElementById('upload-category');
        
        data.categories.forEach(category => {
            const option1 = new Option(category, category);
            const option2 = new Option(category, category);
            categorySelect.add(option1);
            uploadCategorySelect.add(option2);
        });
    } catch (error) {
        console.error('Failed to load categories:', error);
    }
}

function showSettings() {
    document.getElementById('settings-modal').classList.add('active');
}

function hideSettings() {
    document.getElementById('settings-modal').classList.remove('active');
}

function exportData() {
    showNotification('Data export functionality coming soon!', 'info');
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 10000;
        transition: all 0.3s ease;
        max-width: 400px;
    `;
    
    // Set color based on type
    switch(type) {
        case 'success': notification.style.background = '#059669'; break;
        case 'error': notification.style.background = '#dc2626'; break;
        case 'warning': notification.style.background = '#d97706'; break;
        default: notification.style.background = '#2563eb';
    }
    
    notification.textContent = message;
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Check for invite code in URL
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('invite') && urlParams.get('email')) {
    document.getElementById('invite-code').value = urlParams.get('invite');
    document.getElementById('register-email').value = urlParams.get('email');
    switchAuthTab('register');
}
