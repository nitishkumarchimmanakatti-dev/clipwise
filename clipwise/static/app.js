// Clipwise v2 Frontend Engine

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const tabUpload = document.getElementById('tabUpload');
  const tabYoutube = document.getElementById('tabYoutube');
  const uploadInputGroup = document.getElementById('uploadInputGroup');
  const youtubeInputGroup = document.getElementById('youtubeInputGroup');
  const ownershipBanner = document.getElementById('ownershipBanner');
  const ownershipCheckbox = document.getElementById('ownershipCheckbox');
  const youtubeUrl = document.getElementById('youtubeUrl');
  const videoFile = document.getElementById('videoFile');
  const generateForm = document.getElementById('generateForm');
  const submitBtn = document.getElementById('submitBtn');
  const uploadSubmitBtn = document.getElementById('uploadSubmitBtn');
  const maxClips = document.getElementById('maxClips');
  const renderMode = document.getElementById('renderMode');
  const captionColorSelect = document.getElementById('captionColorSelect');
  const useLlm = document.getElementById('useLlm');

  const progressSection = document.getElementById('progressSection');
  const progressBar = document.getElementById('progressBar');
  const progressPercentage = document.getElementById('progressPercentage');
  const currentStepText = document.getElementById('currentStepText');
  const elapsedTimer = document.getElementById('elapsedTimer');
  const cancelJobBtn = document.getElementById('cancelJobBtn');
  const logsConsole = document.getElementById('logsConsole');

  const resultsSection = document.getElementById('resultsSection');
  const clipsGrid = document.getElementById('clipsGrid');
  const downloadApprovedZipBtn = document.getElementById('downloadApprovedZipBtn');
  const filterPills = document.querySelectorAll('.filter-pills .pill');

  // Modals
  const reviewModal = document.getElementById('reviewModal');
  const closeReviewModalBtn = document.getElementById('closeReviewModalBtn');
  const reviewVideoPlayer = document.getElementById('reviewVideoPlayer');
  const reviewClipTitle = document.getElementById('reviewClipTitle');
  const reviewScoreBadge = document.getElementById('reviewScoreBadge');
  const reviewDurationBadge = document.getElementById('reviewDurationBadge');
  const reviewMoodBadge = document.getElementById('reviewMoodBadge');
  const reviewTitleInput = document.getElementById('reviewTitleInput');
  const reviewWhyText = document.getElementById('reviewWhyText');
  const reviewDescInput = document.getElementById('reviewDescInput');
  const reviewMusicSelect = document.getElementById('reviewMusicSelect');
  const reviewColorSelect = document.getElementById('reviewColorSelect');
  const reviewStartInput = document.getElementById('reviewStartInput');
  const reviewEndInput = document.getElementById('reviewEndInput');
  const reRenderBtn = document.getElementById('reRenderBtn');
  const approveBtn = document.getElementById('approveBtn');
  const rejectBtn = document.getElementById('rejectBtn');
  const downloadMp4Btn = document.getElementById('downloadMp4Btn');
  const downloadSrtBtn = document.getElementById('downloadSrtBtn');

  // Auth, History, Logs, Storage
  const authBtn = document.getElementById('authBtn');
  const authBtnText = document.getElementById('authBtnText');
  const loginModal = document.getElementById('loginModal');
  const loginForm = document.getElementById('loginForm');
  const closeLoginModalBtn = document.getElementById('closeLoginModalBtn');
  const loginError = document.getElementById('loginError');

  const viewHistoryBtn = document.getElementById('viewHistoryBtn');
  const historyModal = document.getElementById('historyModal');
  const closeModalBtn = document.getElementById('closeModalBtn');
  const historyList = document.getElementById('historyList');

  const viewLogsBtn = document.getElementById('viewLogsBtn');
  const logsModal = document.getElementById('logsModal');
  const closeLogsModalBtn = document.getElementById('closeLogsModalBtn');
  const logsTableBody = document.getElementById('logsTableBody');

  const viewStorageBtn = document.getElementById('viewStorageBtn');
  const storageModal = document.getElementById('storageModal');
  const closeStorageModalBtn = document.getElementById('closeStorageModalBtn');

  // YouTube Channel Automation
  const youtubeConnectBtn = document.getElementById('youtubeConnectBtn');
  const youtubeBtnText = document.getElementById('youtubeBtnText');
  const youtubeModal = document.getElementById('youtubeModal');
  const closeYoutubeModalBtn = document.getElementById('closeYoutubeModalBtn');
  const ytStatusText = document.getElementById('ytStatusText');
  const ytAuthLink = document.getElementById('ytAuthLink');
  const ytAuthCodeInput = document.getElementById('ytAuthCodeInput');
  const ytSubmitCodeBtn = document.getElementById('ytSubmitCodeBtn');
  const ytClientIdInput = document.getElementById('ytClientIdInput');
  const ytClientSecretInput = document.getElementById('ytClientSecretInput');
  const ytSecretJsonInput = document.getElementById('ytSecretJsonInput');
  const ytSaveCredsBtn = document.getElementById('ytSaveCredsBtn');
  const autoUploadOnApprove = document.getElementById('autoUploadOnApprove');
  const uploadToYoutubeBtn = document.getElementById('uploadToYoutubeBtn');
  const youtubeUploadStatus = document.getElementById('youtubeUploadStatus');
  const storageMetrics = document.getElementById('storageMetrics');
  const triggerCleanupBtn = document.getElementById('triggerCleanupBtn');

  // User Clipping Guidance Prompt & Uploaded Videos Dashboard
  const customPrompt = document.getElementById('customPrompt');
  const uploadedClipsGrid = document.getElementById('uploadedClipsGrid');
  const candidatesCountBadge = document.getElementById('candidatesCountBadge');
  const uploadedColCountBadge = document.getElementById('uploadedColCountBadge');
  const uploadedCountBadge = document.getElementById('uploadedCountBadge');
  const viewUploadedBtn = document.getElementById('viewUploadedBtn');
  const uploadedModal = document.getElementById('uploadedModal');
  const closeUploadedModalBtn = document.getElementById('closeUploadedModalBtn');
  const allUploadedGrid = document.getElementById('allUploadedGrid');

  let currentVideoId = null;
  let currentActiveClip = null;
  let activeTaskId = null;
  let pollInterval = null;
  let timerInterval = null;
  let startTime = null;
  let availableMusicTracks = [];

  // Tab Switching
  tabUpload.addEventListener('click', () => {
    tabUpload.classList.add('active');
    tabYoutube.classList.remove('active');
    uploadInputGroup.classList.remove('hidden');
    youtubeInputGroup.classList.add('hidden');
    ownershipBanner.classList.add('hidden');
    youtubeUrl.removeAttribute('required');
  });

  tabYoutube.addEventListener('click', () => {
    tabYoutube.classList.add('active');
    tabUpload.classList.remove('active');
    youtubeInputGroup.classList.remove('hidden');
    uploadInputGroup.classList.add('hidden');
    ownershipBanner.classList.remove('hidden');
    youtubeUrl.setAttribute('required', 'true');
  });

  // Stopwatch Timer
  function startTimer() {
    if (timerInterval) clearInterval(timerInterval);
    startTime = Date.now();
    elapsedTimer.textContent = '⏱ 0s';
    timerInterval = setInterval(() => {
      if (!startTime) return;
      const elapsed = Math.floor((Date.now() - startTime) / 1000);
      elapsedTimer.textContent = `⏱ ${elapsed}s`;
    }, 1000);
  }

  function stopTimer() {
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = null;
  }

  function updateProgress(percent, step) {
    progressBar.style.width = `${percent}%`;
    progressPercentage.textContent = `${percent}%`;
    currentStepText.textContent = step;
  }

  // Load Music Library
  async function loadMusicCatalog() {
    try {
      const res = await fetch('/api/music/tracks');
      if (res.ok) {
        availableMusicTracks = await res.json();
        reviewMusicSelect.innerHTML = '<option value="none">No Music</option>';
        availableMusicTracks.forEach(t => {
          const opt = document.createElement('option');
          opt.value = t.id;
          opt.textContent = `${t.name} (${t.mood.toUpperCase()})`;
          reviewMusicSelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.error('Failed to load music catalog:', e);
    }
  }
  loadMusicCatalog();

  // Auth Status Check
  async function checkAuthStatus() {
    try {
      const res = await fetch('/api/auth/status');
      if (res.ok) {
        const data = await res.json();
        if (data.auth_required) {
          authBtnText.textContent = data.logged_in ? '🔓 Logout' : '🔒 Login';
        } else {
          authBtn.classList.add('hidden');
        }
      }
    } catch (e) {
      console.error(e);
    }
  }
  checkAuthStatus();

  authBtn.addEventListener('click', async () => {
    if (authBtnText.textContent.includes('Logout')) {
      await fetch('/api/auth/logout', { method: 'POST' });
      checkAuthStatus();
    } else {
      loginModal.classList.remove('hidden');
    }
  });

  closeLoginModalBtn.addEventListener('click', () => loginModal.classList.add('hidden'));

  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    loginError.classList.add('hidden');
    const pwd = document.getElementById('adminPassword').value;
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: pwd })
      });
      if (res.ok) {
        loginModal.classList.add('hidden');
        checkAuthStatus();
      } else {
        const err = await res.json();
        loginError.textContent = err.detail || 'Login failed';
        loginError.classList.remove('hidden');
      }
    } catch (err) {
      loginError.textContent = 'Server connection error';
      loginError.classList.remove('hidden');
    }
  });

  // YouTube Submission Handler
  async function handleYoutubeSubmit() {
    const url = youtubeUrl.value.trim();
    if (!url) {
      alert("Please enter a YouTube video URL first.");
      youtubeUrl.focus();
      return;
    }

    if (!ownershipCheckbox.checked) {
      alert("Copyright confirmation required: Please check 'I own the rights to this video' below the URL.");
      ownershipCheckbox.focus();
      return;
    }

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
          max_clips: parseInt(maxClips.value),
          mode: renderMode.value,
          use_llm: useLlm.checked,
          ownership_confirmed: true,
          caption_color: captionColorSelect.value,
          force: true,
          prompt: customPrompt ? customPrompt.value.trim() : null,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to submit generation job');
      }

      const data = await res.json();
      activeTaskId = data.task_id;
      currentVideoId = data.video_id;
      startPolling(data.task_id, data.video_id);
    } catch (err) {
      stopTimer();
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<span>Generate Clips</span><span class="btn-arrow">→</span>';
      alert(`Submission error: ${err.message}`);
    }
  }

  submitBtn.addEventListener('click', (e) => {
    e.preventDefault();
    handleYoutubeSubmit();
  });

  youtubeUrl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleYoutubeSubmit();
    }
  });

  generateForm.addEventListener('submit', (e) => {
    e.preventDefault();
    if (!youtubeInputGroup.classList.contains('hidden')) {
      handleYoutubeSubmit();
    }
  });

  // Upload Submission
  uploadSubmitBtn.addEventListener('click', async () => {
    const file = videoFile.files[0];
    if (!file) {
      alert('Please select a video file (MP4/MOV) first.');
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
    formData.append('max_clips', maxClips.value);
    formData.append('mode', renderMode.value);
    formData.append('use_llm', useLlm.checked ? 'true' : 'false');
    formData.append('caption_color', captionColorSelect.value);
    formData.append('prompt', customPrompt ? customPrompt.value.trim() : '');

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const data = await res.json();
      activeTaskId = data.task_id;
      currentVideoId = data.video_id;
      startPolling(data.task_id, data.video_id);
    } catch (err) {
      stopTimer();
      uploadSubmitBtn.disabled = false;
      uploadSubmitBtn.innerHTML = '<span>Upload & Generate</span><span class="btn-arrow">→</span>';
      alert(`Upload error: ${err.message}`);
    }
  });

  // Cancel Job
  cancelJobBtn.addEventListener('click', async () => {
    if (!activeTaskId) return;
    if (confirm('Are you sure you want to cancel this processing job?')) {
      await fetch(`/api/task/${activeTaskId}/cancel`, { method: 'POST' });
      currentStepText.textContent = 'Cancelling job...';
    }
  });

  // Polling Engine
  function startPolling(taskId, videoId) {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/task/${taskId}`);
        if (!res.ok) return;

        const task = await res.json();
        updateProgress(task.progress, task.current_step);

        if (task.logs && task.logs.length > 0) {
          logsConsole.innerHTML = task.logs.map(line => `<div>${escapeHtml(line)}</div>`).join('');
          logsConsole.scrollTop = logsConsole.scrollHeight;
        }

        if (task.status === 'completed') {
          clearInterval(pollInterval);
          stopTimer();
          resetSubmitBtns();
          progressSection.classList.add('hidden');
          loadClipsForVideo(videoId);
        } else if (task.status === 'failed' || task.status === 'cancelled') {
          clearInterval(pollInterval);
          stopTimer();
          resetSubmitBtns();
          const errText = (task.error || task.status || '').toLowerCase();
          if (errText.includes('sign in to confirm') || errText.includes('not a bot') || errText.includes('cookies')) {
            alert(
              "⚠️ YouTube Cloud Block Detected\n\n" +
              "YouTube blocks automated downloads on cloud datacenter servers (like Railway/AWS) with a bot challenge.\n\n" +
              "👉 SOLUTION: Please switch to the 'Upload Video (Primary)' tab and upload your MP4/MOV file directly. Direct file uploads are 100% reliable and never blocked by YouTube!\n\n" +
              "(Or run Clipwise locally on your Mac at http://127.0.0.1:8000 where your residential connection is not restricted)."
            );
            // Automatically switch user to the Upload Video tab
            const uploadTab = document.querySelector('[data-tab="upload"]');
            if (uploadTab) uploadTab.click();
          } else {
            alert(`Pipeline ended: ${task.error || task.status}`);
          }
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, 1500);
  }

  function resetSubmitBtns() {
    submitBtn.disabled = false;
    submitBtn.innerHTML = '<span>Generate Clips</span><span class="btn-arrow">→</span>';
    uploadSubmitBtn.disabled = false;
    uploadSubmitBtn.innerHTML = '<span>Upload & Generate</span><span class="btn-arrow">→</span>';
  }

  // Load and Render Clips Grid
  async function loadClipsForVideo(videoId) {
    currentVideoId = videoId;
    try {
      const res = await fetch(`/api/clips/${videoId}`);
      if (!res.ok) throw new Error('Failed to load clips');

      const data = await res.json();
      renderClipsGrid(data.clips || []);
      resultsSection.classList.remove('hidden');
      resultsSection.scrollIntoView({ behavior: 'smooth' });
    } catch (err) {
      alert(`Error loading clips: ${err.message}`);
    }
  }

  function createClipCard(clip, isUploaded) {
    const card = document.createElement('div');
    card.className = `clip-card ${isUploaded ? 'uploaded-card' : ''}`;
    card.dataset.status = isUploaded ? 'uploaded' : (clip.status || 'pending');

    const musicTag = clip.music_used ? `🎵 ${clip.music_track || 'Music'}` : 'No Music';
    const score = clip.hook_score !== undefined ? clip.hook_score : 8.5;

    const uploadedCta = isUploaded && clip.youtube_url ? `
      <div style="margin-top: 10px;">
        <a href="${clip.youtube_url}" target="_blank" class="youtube-live-badge" onclick="event.stopPropagation();">
          ▶ Watch on YouTube Shorts ↗
        </a>
      </div>
    ` : '';

    const statusLabel = isUploaded ? '🚀 UPLOADED' : (clip.status || 'pending').toUpperCase();
    const statusClass = isUploaded ? 'uploaded' : (clip.status || 'pending');

    card.innerHTML = `
      <div class="video-container">
        <video src="${clip.video_url}" preload="metadata" muted playsinline></video>
        <div class="card-overlay">
          <span class="hook-score-badge">★ ${score}</span>
          <span class="duration-badge">${Math.round(clip.duration)}s</span>
        </div>
        <div class="play-hint-icon">▶</div>
      </div>
      <div class="card-content">
        <div class="card-meta">
          <span class="status-badge ${statusClass}">${statusLabel}</span>
          <span class="music-pill">${musicTag}</span>
        </div>
        <h4 class="clip-title">${escapeHtml(clip.title)}</h4>
        <p class="clip-why">${escapeHtml(clip.why_this_clip || 'High engagement hook')}</p>
        ${uploadedCta}
      </div>
    `;

    card.addEventListener('click', () => openReviewModal(clip));
    return card;
  }

  function renderClipsGrid(clips) {
    clipsGrid.innerHTML = '';
    if (uploadedClipsGrid) uploadedClipsGrid.innerHTML = '';

    const candidates = clips.filter(c => c.status !== 'uploaded' && !c.youtube_url);
    const uploaded = clips.filter(c => c.status === 'uploaded' || c.youtube_url);

    if (candidatesCountBadge) candidatesCountBadge.textContent = candidates.length;
    if (uploadedColCountBadge) uploadedColCountBadge.textContent = uploaded.length;

    // 1. Render Candidates Column
    if (candidates.length === 0) {
      clipsGrid.innerHTML = '<div class="empty-column-state"><div class="empty-icon">⚡</div><p>No pending candidates</p><span>All generated clips have been approved or uploaded!</span></div>';
    } else {
      candidates.forEach(clip => {
        clipsGrid.appendChild(createClipCard(clip, false));
      });
    }

    // 2. Render Uploaded Videos Column
    if (uploadedClipsGrid) {
      if (uploaded.length === 0) {
        uploadedClipsGrid.innerHTML = `
          <div class="empty-column-state">
            <div class="empty-icon">📺</div>
            <p>No videos uploaded to YouTube yet from this batch.</p>
            <span>Click "Approve & Upload" in any clip's review modal to publish it straight to your YouTube channel!</span>
          </div>`;
      } else {
        uploaded.forEach(clip => {
          uploadedClipsGrid.appendChild(createClipCard(clip, true));
        });
      }
    }

    updateUploadedCountBadge();
  }

  // Update Navbar Uploaded Count Badge
  async function updateUploadedCountBadge() {
    try {
      const res = await fetch('/api/youtube/uploaded');
      if (res.ok) {
        const data = await res.json();
        if (uploadedCountBadge) uploadedCountBadge.textContent = data.count || 0;
      }
    } catch (e) {
      console.error(e);
    }
  }
  updateUploadedCountBadge();

  // Open All Uploaded Shorts Modal
  if (viewUploadedBtn) {
    viewUploadedBtn.addEventListener('click', async () => {
      try {
        const res = await fetch('/api/youtube/uploaded');
        if (res.ok) {
          const data = await res.json();
          allUploadedGrid.innerHTML = '';
          if (!data.uploaded_clips || data.uploaded_clips.length === 0) {
            allUploadedGrid.innerHTML = '<div class="empty-state" style="grid-column: 1/-1;">No clips uploaded to YouTube yet. Approve and upload clips to see them here!</div>';
          } else {
            data.uploaded_clips.forEach(clip => {
              allUploadedGrid.appendChild(createClipCard(clip, true));
            });
          }
          uploadedModal.classList.remove('hidden');
        }
      } catch (err) {
        alert(`Failed to load uploaded videos: ${err.message}`);
      }
    });
  }

  if (closeUploadedModalBtn) {
    closeUploadedModalBtn.addEventListener('click', () => {
      uploadedModal.classList.add('hidden');
    });
  }

  // Interactive Clip Review Modal
  function openReviewModal(clip) {
    currentActiveClip = clip;
    reviewClipTitle.textContent = clip.title;
    reviewVideoPlayer.src = clip.video_url;
    reviewScoreBadge.textContent = `Hook Score: ${clip.hook_score}/10`;
    reviewDurationBadge.textContent = `${Math.round(clip.duration)}s (${clip.start_formatted} - ${clip.end_formatted})`;
    reviewMoodBadge.textContent = clip.music_used ? `🎵 ${clip.music_track}` : 'No Music';
    reviewTitleInput.value = clip.title;
    reviewWhyText.textContent = clip.why_this_clip || 'Standalone complete thought with clean boundary.';
    reviewDescInput.value = clip.description || '';
    reviewStartInput.value = clip.start;
    reviewEndInput.value = clip.end;

    downloadMp4Btn.href = clip.download_url;
    downloadMp4Btn.setAttribute('download', `${clip.clip_id}.mp4`);
    downloadSrtBtn.href = clip.srt_url;
    downloadSrtBtn.setAttribute('download', `${clip.clip_id}.srt`);

    // Set YouTube status in review modal
    if (clip.youtube_status === 'uploaded' && clip.youtube_url) {
      youtubeUploadStatus.innerHTML = `✅ Uploaded to YouTube! <a href="${clip.youtube_url}" target="_blank" style="color: #63b3ed; text-decoration: underline; font-weight: 600;">View Short ↗</a>`;
      uploadToYoutubeBtn.textContent = '🔄 Re-upload to YouTube';
    } else {
      youtubeUploadStatus.innerHTML = '';
      uploadToYoutubeBtn.textContent = '🚀 Upload to YouTube Shorts (Public)';
    }

    reviewModal.classList.remove('hidden');
    reviewVideoPlayer.play().catch(() => {});
  }

  closeReviewModalBtn.addEventListener('click', () => {
    reviewVideoPlayer.pause();
    reviewModal.classList.add('hidden');
  });

  // Approve / Reject
  approveBtn.addEventListener('click', async () => {
    if (!currentActiveClip) return;
    const autoUpload = autoUploadOnApprove ? autoUploadOnApprove.checked : false;
    await updateClipStatus(currentActiveClip.clip_id, 'approved', autoUpload);
    reviewModal.classList.add('hidden');
  });

  rejectBtn.addEventListener('click', async () => {
    if (!currentActiveClip) return;
    await updateClipStatus(currentActiveClip.clip_id, 'rejected', false);
    reviewModal.classList.add('hidden');
  });

  // Dedicated YouTube Upload Button
  if (uploadToYoutubeBtn) {
    uploadToYoutubeBtn.addEventListener('click', async () => {
      if (!currentActiveClip || !currentVideoId) return;
      uploadToYoutubeBtn.disabled = true;
      youtubeUploadStatus.innerHTML = '⏳ Uploading to YouTube Shorts...';
      try {
        const res = await fetch('/api/youtube/upload', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            video_id: currentVideoId,
            clip_id: currentActiveClip.clip_id,
            title: reviewTitleInput.value.trim(),
            description: reviewDescInput.value.trim(),
            privacy_status: 'public'
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Upload failed');

        youtubeUploadStatus.innerHTML = `✅ Uploaded! <a href="${data.result.url}" target="_blank" style="color: #63b3ed; text-decoration: underline; font-weight: 600;">Open Short ↗</a>`;
        alert(`🎉 Successfully uploaded to YouTube Shorts!\n\nLink: ${data.result.url}`);
        loadClipsForVideo(currentVideoId);
      } catch (err) {
        youtubeUploadStatus.innerHTML = `<span style="color: #fc8181;">❌ ${err.message}</span>`;
        alert(`YouTube Upload Failed:\n${err.message}`);
      } finally {
        uploadToYoutubeBtn.disabled = false;
      }
    });
  }

  async function updateClipStatus(clipId, newStatus, autoUpload = false) {
    try {
      const res = await fetch(`/api/clips/${clipId}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus, auto_upload: autoUpload })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.upload && data.upload.url) {
          alert(`🎉 Clip approved and automatically uploaded to YouTube Shorts!\n\nLink: ${data.upload.url}`);
        } else if (data.upload && data.upload.error) {
          alert(`Clip approved, but YouTube upload failed:\n${data.upload.error}`);
        }
        if (currentVideoId) loadClipsForVideo(currentVideoId);
      }
    } catch (e) {
      console.error(e);
    }
  }

  // Re-Render / Re-Trim Clip
  reRenderBtn.addEventListener('click', async () => {
    if (!currentActiveClip || !currentVideoId) return;

    const newStart = parseFloat(reviewStartInput.value);
    const newEnd = parseFloat(reviewEndInput.value);
    if (isNaN(newStart) || isNaN(newEnd) || newEnd <= newStart) {
      alert('Invalid start or end timestamps.');
      return;
    }

    reRenderBtn.disabled = true;
    reRenderBtn.textContent = 'Rendering...';

    try {
      const res = await fetch(`/api/clips/${currentVideoId}/${currentActiveClip.clip_id}/re-render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start: newStart,
          end: newEnd,
          music_track_id: reviewMusicSelect.value,
          caption_color: reviewColorSelect.value,
        })
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Re-rendering failed');
      }

      const data = await res.json();
      alert('Clip re-rendered successfully with new settings!');
      reviewVideoPlayer.src = `${currentActiveClip.video_url}?t=${Date.now()}`;
      reviewVideoPlayer.play();
      loadClipsForVideo(currentVideoId);
    } catch (err) {
      alert(`Error re-rendering: ${err.message}`);
    } finally {
      reRenderBtn.disabled = false;
      reRenderBtn.textContent = '🔄 Re-render Clip';
    }
  });

  // Download Approved ZIP
  downloadApprovedZipBtn.addEventListener('click', () => {
    if (!currentVideoId) {
      alert('No video loaded.');
      return;
    }
    window.location.href = `/api/clips/${currentVideoId}/export-zip`;
  });

  // History / Past Projects
  viewHistoryBtn.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/history');
      if (res.ok) {
        const list = await res.json();
        renderHistoryList(list);
        historyModal.classList.remove('hidden');
      }
    } catch (e) {
      console.error(e);
    }
  });

  closeModalBtn.addEventListener('click', () => historyModal.classList.add('hidden'));

  function renderHistoryList(items) {
    historyList.innerHTML = '';
    if (items.length === 0) {
      historyList.innerHTML = '<div class="empty-state">No processed projects yet.</div>';
      return;
    }

    items.forEach(item => {
      const row = document.createElement('div');
      row.className = 'history-item';
      row.innerHTML = `
        <div class="history-item-info">
          <h4>${escapeHtml(item.title)}</h4>
          <p>${item.channel ? item.channel + ' • ' : ''}${item.clip_count} clips generated</p>
        </div>
        <div class="history-item-actions">
          <button class="btn btn-secondary btn-sm load-proj-btn">Open</button>
          <button class="btn btn-danger btn-sm del-proj-btn">Delete</button>
        </div>
      `;

      row.querySelector('.load-proj-btn').addEventListener('click', () => {
        historyModal.classList.add('hidden');
        loadClipsForVideo(item.video_id);
      });

      row.querySelector('.del-proj-btn').addEventListener('click', async () => {
        const confirmation = prompt(`To permanently delete '${item.title}', type DELETE below:`);
        if (confirmation === 'DELETE') {
          const delRes = await fetch(`/api/video/${item.video_id}/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ confirmation: 'DELETE' })
          });
          if (delRes.ok) {
            row.remove();
          } else {
            alert('Delete rejected.');
          }
        }
      });

      historyList.appendChild(row);
    });
  }

  // Run History Log
  viewLogsBtn.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/log');
      if (res.ok) {
        const logs = await res.json();
        logsTableBody.innerHTML = '';
        logs.forEach(l => {
          const tr = document.createElement('tr');
          tr.innerHTML = `
            <td>${l.timestamp ? l.timestamp.split('.')[0] : ''}</td>
            <td><code>${l.video_id || ''}</code></td>
            <td>${l.source_type || 'youtube'}</td>
            <td>${l.clips_generated || 0}</td>
            <td><strong>${l.status || ''}</strong></td>
            <td>${escapeHtml(l.details || '')}</td>
          `;
          logsTableBody.appendChild(tr);
        });
        logsModal.classList.remove('hidden');
      }
    } catch (e) {
      console.error(e);
    }
  });

  closeLogsModalBtn.addEventListener('click', () => logsModal.classList.add('hidden'));

  // Storage Information
  viewStorageBtn.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/storage');
      if (res.ok) {
        const stats = await res.json();
        storageMetrics.innerHTML = `
          <p><strong>Rendered Output Storage:</strong> ${stats.output_mb} MB</p>
          <p><strong>Original Downloads Storage:</strong> ${stats.originals_mb} MB</p>
          <p><strong>Disk Free:</strong> ${stats.disk_free_gb} GB / ${stats.disk_total_gb} GB (${stats.disk_used_percent}% used)</p>
          <p class="text-muted"><small>Originals auto-expire after 7 days to conserve disk space.</small></p>
        `;
        storageModal.classList.remove('hidden');
      }
    } catch (e) {
      console.error(e);
    }
  });

  closeStorageModalBtn.addEventListener('click', () => storageModal.classList.add('hidden'));

  triggerCleanupBtn.addEventListener('click', async () => {
    const res = await fetch('/api/storage/cleanup', { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      alert(`Auto-cleanup completed: ${data.cleaned_items} expired items removed.`);
      storageModal.classList.add('hidden');
    }
  });

  // Filter Pills (All / Pending / Approved / Rejected)
  filterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      filterPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      const filter = pill.dataset.filter;
      const cards = document.querySelectorAll('.clip-card');
      cards.forEach(card => {
        if (filter === 'all' || card.dataset.status === filter) {
          card.classList.remove('hidden');
        } else {
          card.classList.add('hidden');
        }
      });
    });
  });

  // YouTube Channel Automation Handlers
  if (youtubeConnectBtn) {
    youtubeConnectBtn.addEventListener('click', () => {
      youtubeModal.classList.remove('hidden');
      checkYouTubeStatus();
    });
  }

  if (closeYoutubeModalBtn) {
    closeYoutubeModalBtn.addEventListener('click', () => {
      youtubeModal.classList.add('hidden');
    });
  }

  async function checkYouTubeStatus() {
    try {
      const res = await fetch('/api/youtube/status');
      if (!res.ok) return;
      const data = await res.json();
      if (data.authenticated) {
        if (youtubeBtnText) youtubeBtnText.textContent = `🟢 ${data.channel_title || 'YouTube'}`;
        if (ytStatusText) {
          ytStatusText.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px;">
              ${data.thumbnail ? `<img src="${data.thumbnail}" style="width: 44px; height: 44px; border-radius: 50%;">` : ''}
              <div>
                <strong style="color: #68d391; font-size: 1rem;">✅ Connected: ${escapeHtml(data.channel_title)}</strong>
                <div style="font-size: 0.82rem; color: #a0aec0;">${data.subscriber_count || '0'} subscribers • ${data.video_count || '0'} videos</div>
              </div>
            </div>
          `;
        }
      } else {
        if (youtubeBtnText) youtubeBtnText.textContent = '📺 Connect YouTube';
        if (ytStatusText) {
          ytStatusText.innerHTML = `
            <span style="color: #ecc94b; font-weight: 600;">⚪ Not Connected to YouTube</span>
            <div style="font-size: 0.82rem; color: #a0aec0; margin-top: 4px;">Click the button below to authorize Clipwise with your YouTube account.</div>
          `;
        }
        fetchAuthUrl();
      }
    } catch (e) {
      console.error('Failed to check YouTube status:', e);
    }
  }

  async function fetchAuthUrl() {
    try {
      const res = await fetch('/api/youtube/auth/url', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        if (ytAuthLink) ytAuthLink.href = data.auth_url;
      }
    } catch (e) {
      console.error('Failed fetching auth url:', e);
    }
  }

  if (ytSubmitCodeBtn) {
    ytSubmitCodeBtn.addEventListener('click', async () => {
      const code = ytAuthCodeInput.value.trim();
      if (!code) {
        alert('Please paste the Google Authorization code first.');
        return;
      }
      ytSubmitCodeBtn.disabled = true;
      try {
        const res = await fetch('/api/youtube/auth/callback', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code: code })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Authorization failed');
        alert('🎉 YouTube channel successfully connected!');
        ytAuthCodeInput.value = '';
        checkYouTubeStatus();
      } catch (err) {
        alert(`Authentication Error: ${err.message}`);
      } finally {
        ytSubmitCodeBtn.disabled = false;
      }
    });
  }

  if (ytSaveCredsBtn) {
    ytSaveCredsBtn.addEventListener('click', async () => {
      const clientId = ytClientIdInput.value.trim();
      const clientSecret = ytClientSecretInput.value.trim();
      const secretJson = ytSecretJsonInput.value.trim();

      if (!secretJson && (!clientId || !clientSecret)) {
        alert('Please enter Client ID & Secret or paste client_secret.json content.');
        return;
      }

      ytSaveCredsBtn.disabled = true;
      try {
        const res = await fetch('/api/youtube/auth/credentials', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            client_id: clientId || null,
            client_secret: clientSecret || null,
            credentials_json: secretJson || null
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed saving credentials');
        alert('Credentials saved! You can now authorize your channel.');
        fetchAuthUrl();
      } catch (err) {
        alert(`Error saving credentials: ${err.message}`);
      } finally {
        ytSaveCredsBtn.disabled = false;
      }
    });
  }

  // Initial YouTube connection check
  checkYouTubeStatus();

  function escapeHtml(text) {
    if (!text) return '';
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
});
