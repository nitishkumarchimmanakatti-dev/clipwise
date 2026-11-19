/**
 * Clipwise Frontend Application Logic
 */

let currentTaskId = null;
let pollInterval = null;
let allClips = [];
let currentFilter = 'all';

// DOM Elements
const generateForm = document.getElementById('generateForm');
const youtubeUrlInput = document.getElementById('youtubeUrl');
const maxClipsSelect = document.getElementById('maxClips');
const renderModeSelect = document.getElementById('renderMode');
const useLlmCheckbox = document.getElementById('useLlm');
const submitBtn = document.getElementById('submitBtn');

const progressSection = document.getElementById('progressSection');
const progressBar = document.getElementById('progressBar');
const progressPercentage = document.getElementById('progressPercentage');
const currentStepText = document.getElementById('currentStepText');
const logsConsole = document.getElementById('logsConsole');
const elapsedTimer = document.getElementById('elapsedTimer');

let startTime = null;
let timerInterval = null;

function startTimer() {
  if (timerInterval) clearInterval(timerInterval);
  startTime = Date.now();
  if (elapsedTimer) elapsedTimer.textContent = '⏱ 0s';
  timerInterval = setInterval(() => {
    if (!startTime) return;
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    if (elapsedTimer) elapsedTimer.textContent = `⏱ ${elapsed}s`;
  }, 1000);
}

function stopTimer() {
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = null;
}

const resultsSection = document.getElementById('resultsSection');
const clipsGrid = document.getElementById('clipsGrid');
const filterPills = document.querySelectorAll('.filter-pills .pill');

const viewHistoryBtn = document.getElementById('viewHistoryBtn');
const historyModal = document.getElementById('historyModal');
const closeModalBtn = document.getElementById('closeModalBtn');
const historyList = document.getElementById('historyList');

// Form Submission
generateForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const url = youtubeUrlInput.value.trim();
  if (!url) return;

  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span>Processing...</span>';
  
  progressSection.classList.remove('hidden');
  resultsSection.classList.add('hidden');
  logsConsole.innerHTML = '';
  updateProgress(5, 'Submitting job...');
  startTimer();

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url,
        max_clips: parseInt(maxClipsSelect.value),
        mode: renderModeSelect.value,
        use_llm: useLlmCheckbox.checked,
        force: false
      })
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to submit generation task');
    }

    const data = await res.json();
    currentTaskId = data.task_id;
    startPolling(currentTaskId, data.video_id);
  } catch (err) {
    alert(`Error: ${err.message}`);
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<span>Generate Clips</span><span class="btn-arrow">→</span>';
    progressSection.classList.add('hidden');
  }
});

function updateProgress(percent, text) {
  progressBar.style.width = `${percent}%`;
  progressPercentage.textContent = `${percent}%`;
  if (text) currentStepText.textContent = text;
}

let consecutivePollErrors = 0;

function startPolling(taskId, videoId) {
  if (pollInterval) clearInterval(pollInterval);
  consecutivePollErrors = 0;

  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/task/${taskId}`);
      if (!res.ok) {
        consecutivePollErrors++;
        if (consecutivePollErrors > 6) {
          clearInterval(pollInterval);
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<span>Generate Clips</span><span class="btn-arrow">→</span>';
          alert('Pipeline task was interrupted. Please try again.');
        }
        return;
      }
      consecutivePollErrors = 0;

      const task = await res.json();
      updateProgress(task.progress, task.current_step);

      // Update logs
      if (task.logs && task.logs.length > 0) {
        logsConsole.innerHTML = task.logs.map(line => `<div>${escapeHtml(line)}</div>`).join('');
        logsConsole.scrollTop = logsConsole.scrollHeight;
      }

      if (task.status === 'completed') {
        clearInterval(pollInterval);
        stopTimer();
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Generate Clips</span><span class="btn-arrow">→</span>';
        progressSection.classList.add('hidden');
        loadClipsForVideo(videoId);
      } else if (task.status === 'failed') {
        clearInterval(pollInterval);
        stopTimer();
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Generate Clips</span><span class="btn-arrow">→</span>';
        alert(`Pipeline error: ${task.error}`);
      }
    } catch (e) {
      console.error('Polling error', e);
    }
  }, 1200);
}

async function loadClipsForVideo(videoId) {
  try {
    const res = await fetch(`/api/clips/${videoId}`);
    if (!res.ok) throw new Error('Could not fetch clips');
    const data = await res.json();
    allClips = data.clips || [];
    renderClipsGrid();
    resultsSection.classList.remove('hidden');
    resultsSection.scrollIntoView({ behavior: 'smooth' });
  } catch (err) {
    console.error(err);
  }
}

function renderClipsGrid() {
  clipsGrid.innerHTML = '';
  const filtered = allClips.filter(c => {
    if (currentFilter === 'all') return true;
    return c.status === currentFilter;
  });

  if (filtered.length === 0) {
    clipsGrid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; color: #94a3b8; padding: 40px;">No clips found in this filter category.</div>';
    return;
  }

  filtered.forEach(clip => {
    const card = document.createElement('div');
    card.className = 'clip-card';
    card.id = `card-${clip.clip_id}`;

    const hookScore = clip.hook_score || 0;
    const scoreEmoji = hookScore >= 8.5 ? '🔥' : hookScore >= 7.0 ? '⚡' : '✨';

    card.innerHTML = `
      <div class="video-container">
        <video src="${clip.video_url}" controls playsinline preload="metadata"></video>
        <div class="hook-badge">${scoreEmoji} ${hookScore.toFixed(1)}/10 Hook</div>
        <div class="status-badge status-${clip.status}">${clip.status}</div>
      </div>
      <div class="clip-content">
        <div class="clip-meta-top">
          <span>⏱ ${clip.duration}s (${clip.start_formatted} - ${clip.end_formatted})</span>
        </div>
        <h4 class="clip-title">${escapeHtml(clip.title)}</h4>
        <div class="hashtags-container">
          ${(clip.hashtags || []).map(tag => `<span class="hashtag-pill" onclick="copyText('${tag}')">${tag}</span>`).join('')}
        </div>
        <div class="card-actions">
          <button class="btn btn-approve" onclick="updateStatus('${clip.clip_id}', 'approved')">✓ Approve</button>
          <button class="btn btn-reject" onclick="updateStatus('${clip.clip_id}', 'rejected')">✗ Reject</button>
          <a href="${clip.download_url}" class="btn-download" download title="Download MP4">💾</a>
        </div>
      </div>
    `;
    clipsGrid.appendChild(card);
  });
}

// Inline Clip Approval & Rejection
async function updateStatus(clipId, newStatus) {
  try {
    const res = await fetch(`/api/clips/${clipId}/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (!res.ok) throw new Error('Status update failed');

    // Update local cache
    const match = allClips.find(c => c.clip_id === clipId);
    if (match) match.status = newStatus;

    renderClipsGrid();
  } catch (err) {
    alert(`Could not update clip status: ${err.message}`);
  }
}

// Filter Tabs
filterPills.forEach(pill => {
  pill.addEventListener('click', () => {
    filterPills.forEach(p => p.classList.remove('active'));
    pill.classList.add('active');
    currentFilter = pill.dataset.filter;
    renderClipsGrid();
  });
});

// History Library Modal
viewHistoryBtn.addEventListener('click', async () => {
  try {
    const res = await fetch('/api/history');
    if (!res.ok) throw new Error('Could not load history');
    const history = await res.json();

    if (history.length === 0) {
      historyList.innerHTML = '<p style="color: #94a3b8;">No past projects found yet.</p>';
    } else {
      historyList.innerHTML = history.map(item => `
        <div class="history-item" style="display:flex; justify-content:space-between; align-items:center; padding: 12px; border-bottom: 1px solid rgba(255,255,255,0.08); cursor: pointer;" onclick="openProject('${item.video_id}')">
          <div>
            <strong style="color: #fff; font-size: 14px;">${escapeHtml(item.title)}</strong>
            <p style="color: #94a3b8; font-size: 12px;">${item.channel} • ${item.clip_count} clips</p>
          </div>
          <button class="btn btn-secondary" style="font-size: 11px;">Open</button>
        </div>
      `).join('');
    }

    historyModal.classList.remove('hidden');
  } catch (err) {
    alert(err.message);
  }
});

function openProject(videoId) {
  historyModal.classList.add('hidden');
  loadClipsForVideo(videoId);
}

closeModalBtn.addEventListener('click', () => {
  historyModal.classList.add('hidden');
});

// Tab Switching (YouTube vs Upload)
const tabYoutube = document.getElementById('tabYoutube');
const tabUpload = document.getElementById('tabUpload');
const youtubeInputGroup = document.getElementById('youtubeInputGroup');
const uploadInputGroup = document.getElementById('uploadInputGroup');
const videoFileInput = document.getElementById('videoFile');
const uploadSubmitBtn = document.getElementById('uploadSubmitBtn');

if (tabYoutube && tabUpload) {
  tabYoutube.addEventListener('click', () => {
    tabYoutube.classList.add('active');
    tabUpload.classList.remove('active');
    youtubeInputGroup.classList.remove('hidden');
    uploadInputGroup.classList.add('hidden');
  });

  tabUpload.addEventListener('click', () => {
    tabUpload.classList.add('active');
    tabYoutube.classList.remove('active');
    uploadInputGroup.classList.remove('hidden');
    youtubeInputGroup.classList.add('hidden');
  });
}

// File Upload Handler
if (uploadSubmitBtn) {
  uploadSubmitBtn.addEventListener('click', async () => {
    const file = videoFileInput.files[0];
    if (!file) {
      alert('Please select a video file (MP4, MOV, WEBM) first.');
      return;
    }

    uploadSubmitBtn.disabled = true;
    uploadSubmitBtn.innerHTML = '<span>Uploading...</span>';
    progressSection.classList.remove('hidden');
    resultsSection.classList.add('hidden');
    logsConsole.innerHTML = '';
    updateProgress(5, 'Uploading local video...');
    startTimer();

    const formData = new FormData();
    formData.append('file', file);
    formData.append('max_clips', maxClipsSelect.value);
    formData.append('mode', renderModeSelect.value);
    formData.append('use_llm', useLlmCheckbox.checked);

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const data = await res.json();
      currentTaskId = data.task_id;
      startPolling(currentTaskId, data.video_id);
    } catch (err) {
      alert(`Error: ${err.message}`);
      uploadSubmitBtn.disabled = false;
      uploadSubmitBtn.innerHTML = '<span>Upload & Generate</span><span class="btn-arrow">→</span>';
      progressSection.classList.add('hidden');
    }
  });
}

// Cookies Modal Handlers
const openCookiesBtn = document.getElementById('openCookiesBtn');
const cookiesModal = document.getElementById('cookiesModal');
const closeCookiesBtn = document.getElementById('closeCookiesBtn');
const saveCookiesBtn = document.getElementById('saveCookiesBtn');
const cookiesInput = document.getElementById('cookiesInput');
const cookiesStatus = document.getElementById('cookiesStatus');

if (openCookiesBtn && cookiesModal) {
  openCookiesBtn.addEventListener('click', () => {
    cookiesModal.classList.remove('hidden');
    cookiesStatus.textContent = '';
  });

  closeCookiesBtn.addEventListener('click', () => {
    cookiesModal.classList.add('hidden');
  });

  saveCookiesBtn.addEventListener('click', async () => {
    const content = cookiesInput.value.trim();
    if (!content) {
      alert('Please paste cookie content.');
      return;
    }
    saveCookiesBtn.disabled = true;
    saveCookiesBtn.textContent = 'Saving...';
    try {
      const res = await fetch('/api/cookies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cookies: content })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to save');
      cookiesStatus.style.color = '#10b981';
      cookiesStatus.textContent = '✓ Saved! Server now authenticated.';
      setTimeout(() => {
        cookiesModal.classList.add('hidden');
      }, 1500);
    } catch (err) {
      cookiesStatus.style.color = '#ef4444';
      cookiesStatus.textContent = `Error: ${err.message}`;
    } finally {
      saveCookiesBtn.disabled = false;
      saveCookiesBtn.textContent = 'Save Cookies & Enable';
    }
  });
}

function copyText(text) {
  navigator.clipboard.writeText(text);
  alert(`Copied ${text} to clipboard!`);
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
