const player = document.getElementById('player');
const youtubePlayerContainer = document.getElementById('youtube-player-container');
const searchInput = document.getElementById('search-input');
const searchBtn = document.getElementById('search-btn');
const resultsSection = document.getElementById('results-section');
const resultsGrid = document.getElementById('results-grid');
const loader = document.getElementById('search-loader');
const playlistItems = document.getElementById('playlist-items');
const nowPlayingTitle = document.getElementById('now-playing-title');
const karaokeKnob = document.getElementById('karaoke-knob');
const karaokeModeSelector = document.getElementById('karaoke-mode-selector');
const labelGuide = document.getElementById('label-guide');
const labelSinging = document.getElementById('label-singing');

const exportBtn = document.getElementById('export-playlist-btn');
const importBtn = document.getElementById('import-playlist-btn');

const skipBtn = document.getElementById('skip-btn');
const volumeSlider = document.getElementById('volume-slider');
const clearPlaylistBtn = document.getElementById('clear-playlist-btn');
const playerModeBtn = document.getElementById('player-mode-btn');
const playerModeText = document.getElementById('player-mode-text');

let playlist = [];
let currentIndex = -1;
let playRequestId = 0;

// YouTube IFrame Player
let ytPlayer = null;
let ytPlayerReady = false;
let useYouTubePlayer = true; // Use YouTube embed by default (more reliable)

// Player mode toggle handler
if (playerModeBtn) {
    playerModeBtn.addEventListener('click', () => {
        useYouTubePlayer = !useYouTubePlayer;
        updatePlayerModeUI();
        
        // If currently playing, restart with new mode
        if (currentIndex >= 0 && playlist.length > 0) {
            playSong(currentIndex);
        }
    });
}

function updatePlayerModeUI() {
    if (playerModeText) {
        playerModeText.textContent = useYouTubePlayer ? 'YouTube' : 'Karaoke';
    }
    if (playerModeBtn) {
        const icon = playerModeBtn.querySelector('i');
        if (icon) {
            icon.className = useYouTubePlayer ? 'fab fa-youtube' : 'fas fa-microphone';
        }
        playerModeBtn.style.background = useYouTubePlayer 
            ? 'linear-gradient(135deg, #ef4444, #dc2626)' 
            : 'linear-gradient(135deg, #10b981, #059669)';
    }
    // Show/hide karaoke mode toggle based on player mode
    if (karaokeModeSelector) {
        karaokeModeSelector.style.opacity = useYouTubePlayer ? '0.5' : '1';
        karaokeModeSelector.style.pointerEvents = useYouTubePlayer ? 'none' : 'auto';
        karaokeModeSelector.title = useYouTubePlayer ? 'Switch to Karaoke mode to enable vocal removal' : 'Toggle vocal removal';
    }
}

// Initialize UI state
updatePlayerModeUI();

// YouTube API callback - called automatically when API is ready
window.onYouTubeIframeAPIReady = function() {
    logDebug('YouTube IFrame API Ready');
    ytPlayerReady = true;
};

function initYouTubePlayer(videoId) {
    return new Promise((resolve, reject) => {
        if (ytPlayer) {
            // Player already exists, just load new video
            ytPlayer.loadVideoById(videoId);
            resolve();
            return;
        }

        // Create new player
        ytPlayer = new YT.Player('youtube-player', {
            height: '100%',
            width: '100%',
            videoId: videoId,
            playerVars: {
                'playsinline': 1,
                'autoplay': 1,
                'controls': 1,
                'modestbranding': 1,
                'rel': 0,
                'fs': 1
            },
            events: {
                'onReady': (event) => {
                    logDebug('YouTube Player Ready');
                    event.target.setVolume(volumeSlider.value);
                    resolve();
                },
                'onStateChange': onYouTubePlayerStateChange,
                'onError': (event) => {
                    logDebug(`YouTube Player Error: ${event.data}`);
                    reject(new Error(`YouTube error code: ${event.data}`));
                }
            }
        });
    });
}

function onYouTubePlayerStateChange(event) {
    // YT.PlayerState: ENDED = 0, PLAYING = 1, PAUSED = 2, BUFFERING = 3, CUED = 5
    if (event.data === YT.PlayerState.ENDED) {
        logDebug('YouTube video ended');
        playNext();
    }
}

function logDebug(msg) {
    // Only console log now that the debug UI is removed
    console.log(`[DEBUG] ${msg}`);
}

// ============================================
// API Layer - Supports both Web and Desktop modes
// ============================================
const API = {
    // Check if running in web mode (Flask) or desktop mode (Eel)
    isWebMode: () => typeof eel === 'undefined' || window.WEB_MODE === true,

    // Search YouTube for videos
    searchYouTube: async (query) => {
        if (API.isWebMode()) {
            const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Search failed');
            }
            return response.json();
        } else {
            return eel.search_youtube(query)();
        }
    },

    // Get video info from URL
    getVideoInfo: async (url) => {
        if (API.isWebMode()) {
            const response = await fetch(`/api/video_info?url=${encodeURIComponent(url)}`);
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to get video info');
            }
            return response.json();
        } else {
            return eel.get_video_info(url)();
        }
    },

    // Get stream URL for video
    getStreamUrl: async (videoId) => {
        if (API.isWebMode()) {
            const response = await fetch(`/api/stream_url?id=${encodeURIComponent(videoId)}`);
            const data = await response.json();
            // Server signals that proxy is not available (e.g. on Render)
            if (data.proxy_unavailable) {
                const err = new Error('proxy_unavailable');
                err.proxy_unavailable = true;
                throw err;
            }
            if (!response.ok) {
                throw new Error(data.error || 'Failed to get stream URL');
            }
            return data.url;
        } else {
            return eel.get_stream_url(videoId)();
        }
    },

    // Get subtitles/captions for video
    getSubtitles: async (videoId, title = '') => {
        if (API.isWebMode()) {
            const titleParam = title ? `&title=${encodeURIComponent(title)}` : '';
            const response = await fetch(`/api/subtitles?id=${encodeURIComponent(videoId)}${titleParam}`);
            if (!response.ok) {
                return { available: false, lyrics: '' };
            }
            return response.json();
        } else {
            // For desktop mode, we'd need to implement this in main.py
            return { available: false, lyrics: '' };
        }
    }
};

// ============================================
// Karaoke Lyrics System (Simplified - Static Display)
// ============================================
const lyricsBtn = document.getElementById('lyrics-btn');
const lyricsDisplay = document.getElementById('lyrics-display');
const lyricsContent = document.getElementById('lyrics-content');
const lyricsSource = document.getElementById('lyrics-source');
const editLyricsBtn = document.getElementById('edit-lyrics-btn');

// Modal elements
const lyricsModal = document.getElementById('lyrics-modal');
const modalClose = document.getElementById('modal-close');
const modalCancel = document.getElementById('modal-cancel');
const modalSave = document.getElementById('modal-save');
const editArtist = document.getElementById('edit-artist');
const editTrack = document.getElementById('edit-track');
const editLyrics = document.getElementById('edit-lyrics');

let lyricsVisible = true;
let currentLyricsText = '';
let currentVideoId = '';
let currentArtist = '';
let currentTrack = '';

// Toggle lyrics visibility
if (lyricsBtn) {
    lyricsBtn.addEventListener('click', () => {
        lyricsVisible = !lyricsVisible;
        if (lyricsDisplay) lyricsDisplay.classList.toggle('collapsed', !lyricsVisible);
        lyricsBtn.classList.toggle('active', lyricsVisible);
    });
}

// ============================================
// Lyrics Modal Handlers
// ============================================
function openLyricsModal() {
    if (lyricsModal) {
        // Pre-fill with current info
        if (editArtist) editArtist.value = currentArtist || '';
        if (editTrack) editTrack.value = currentTrack || '';
        if (editLyrics) editLyrics.value = currentLyricsText || '';
        lyricsModal.classList.remove('hidden');
    }
}

function closeLyricsModal() {
    if (lyricsModal) {
        lyricsModal.classList.add('hidden');
    }
}

async function saveLyricsFromModal() {
    const artist = editArtist?.value?.trim() || '';
    const track = editTrack?.value?.trim() || '';
    const lyrics = editLyrics?.value?.trim() || '';
    
    if (!lyrics) {
        alert('Please enter lyrics');
        return;
    }
    
    try {
        const response = await fetch('/api/save_lyrics', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                video_id: currentVideoId,
                artist: artist,
                track: track,
                lyrics: lyrics
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Update current display
            currentArtist = artist;
            currentTrack = track;
            currentLyricsText = lyrics;
            renderLyrics();
            updateSourceLabel('database');
            closeLyricsModal();
            logDebug('Lyrics saved to database');
        } else {
            alert('Save failed: ' + (data.error || 'Unknown error'));
        }
    } catch (err) {
        console.error('Save lyrics error:', err);
        alert('Save failed: ' + err.message);
    }
}

// Modal event listeners
if (editLyricsBtn) {
    editLyricsBtn.addEventListener('click', openLyricsModal);
}

if (modalClose) {
    modalClose.addEventListener('click', closeLyricsModal);
}

if (modalCancel) {
    modalCancel.addEventListener('click', closeLyricsModal);
}

if (modalSave) {
    modalSave.addEventListener('click', saveLyricsFromModal);
}

// Close modal when clicking outside
if (lyricsModal) {
    lyricsModal.addEventListener('click', (e) => {
        if (e.target === lyricsModal) {
            closeLyricsModal();
        }
    });
}

// ============================================
// Lyrics Loading and Display (Simplified)
// ============================================

function updateSourceLabel(source) {
    if (lyricsSource) {
        let label = '';
        if (source.includes('cached')) {
            label = '📦 ' + source;
        } else if (source === 'database' || source === 'manual') {
            label = '💾 Saved';
        } else if (source.includes('netease')) {
            label = '🎵 NetEase';
        } else if (source.includes('kugou')) {
            label = '🎵 Kugou';
        } else if (source.includes('lrclib')) {
            label = '🎵 LRCLIB';
        } else if (source.includes('lyrics.ovh')) {
            label = '📝 lyrics.ovh';
        } else {
            label = source || '';
        }
        lyricsSource.textContent = label;
    }
}

// Load lyrics for a video (simplified - returns plain text)
async function loadLyrics(videoId, videoTitle = '') {
    if (lyricsContent) lyricsContent.innerHTML = '<div class="lyrics-loading">Searching for lyrics...</div>';
    currentLyricsText = '';
    currentVideoId = videoId;

    try {
        // Pass title to speed up the search (avoids yt-dlp lookup)
        const data = await API.getSubtitles(videoId, videoTitle);

        // Update current info
        currentArtist = data.artist || '';
        currentTrack = data.track || '';
        
        // Update source label
        updateSourceLabel(data.source || '');

        if (!data.available || !data.lyrics) {
            if (lyricsContent) lyricsContent.innerHTML = `
                <p class="lyrics-unavailable">
                    🎵 No lyrics found for this song<br>
                    <small>Click "Edit" to add lyrics manually</small>
                </p>`;
            return;
        }

        currentLyricsText = data.lyrics;
        renderLyrics();
        
        logDebug(`Loaded lyrics from ${data.source}`);

    } catch (err) {
        console.error('Failed to load lyrics:', err);
        if (lyricsContent) lyricsContent.innerHTML = '<p class="lyrics-unavailable">Failed to load lyrics</p>';
    }
}

// Render lyrics as simple scrollable text
function renderLyrics() {
    if (!lyricsContent) return;
    
    if (!currentLyricsText) {
        lyricsContent.innerHTML = '<p class="lyrics-placeholder">🎤 Lyrics will appear when playing</p>';
        return;
    }

    // Display lyrics as simple preformatted text
    lyricsContent.innerHTML = `<div class="lyrics-text">${currentLyricsText.replace(/\n/g, '<br>')}</div>`;
}

// Clear lyrics when stopping
function clearLyrics() {
    currentLyricsText = '';
    currentVideoId = '';
    currentArtist = '';
    currentTrack = '';
    if (lyricsContent) lyricsContent.innerHTML = '<p class="lyrics-placeholder">🎤 Lyrics will appear when playing</p>';
    if (lyricsSource) lyricsSource.textContent = '';
}

// Web Audio API Context
let audioCtx;
let source;
let splitter;
let merger;
let leftGain;
let rightGain;
let inverter;
let dryGain; // Original audio gain
let wetGain; // Processed audio gain

function initAudio() {
    if (audioCtx) return;
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    source = audioCtx.createMediaElementSource(player);

    splitter = audioCtx.createChannelSplitter(2);
    merger = audioCtx.createChannelMerger(2);

    // Create an inverter for the right channel
    inverter = audioCtx.createGain();
    inverter.gain.value = -1;

    // Nodes for "Karaoke" path (L - R)
    // L -> Merger[0]
    // R -> Inverter -> Merger[0]
    // This makes Merger[0] = L - R

    dryGain = audioCtx.createGain();
    wetGain = audioCtx.createGain();

    // Default state: Dry only
    dryGain.gain.value = 1;
    wetGain.gain.value = 0;

    source.connect(dryGain);
    dryGain.connect(audioCtx.destination);

    // Karaoke Path
    source.connect(splitter);

    // Right channel sum (mono to both)
    // Create L-R on both channels
    splitter.connect(merger, 0, 0); // L -> Left
    splitter.connect(inverter, 1);  // R -> Inverter
    inverter.connect(merger, 0, 0); // -R -> Left (Left = L - R)

    splitter.connect(merger, 0, 1); // L -> Right
    inverter.connect(merger, 0, 1); // -R -> Right (Right = L - R)

    // Gain compensation for L-R
    const boost = audioCtx.createGain();
    boost.gain.value = 1.5;

    merger.connect(boost);
    boost.connect(wetGain);
    wetGain.connect(audioCtx.destination);
}

searchBtn.addEventListener('click', async () => {
    const query = searchInput.value.trim();
    if (!query) return;

    loader.style.display = 'block';
    searchBtn.disabled = true;

    try {
        if (query.includes('youtube.com/') || query.includes('youtu.be/')) {
            // Direct URL
            const videoInfo = await API.getVideoInfo(query);
            if (videoInfo) {
                addToPlaylist(videoInfo);
                searchInput.value = '';
            } else {
                alert('Unable to get video info. Please check the URL.');
            }
        } else {
            // Search keyword
            const results = await API.searchYouTube(query);
            if (results && results.length > 0) {
                displayResults(results);
            } else {
                alert('No results found. Try different keywords.');
            }
        }
    } catch (err) {
        console.error('API call error:', err);
        alert('Search error: ' + err.message);
    } finally {
        loader.style.display = 'none';
        searchBtn.disabled = false;
    }
});

function displayResults(results) {
    resultsGrid.innerHTML = '';
    resultsSection.style.display = 'block';

    results.forEach(item => {
        const card = document.createElement('div');
        card.className = 'result-card fade-in';
        card.innerHTML = `
      <img src="${item.thumbnail}" alt="${item.title}">
      <div class="info">
        <div class="title">${item.title}</div>
      </div>
    `;
        card.onclick = () => {
            addToPlaylist(item);
            resultsSection.style.display = 'none';
            searchInput.value = '';
        };
        resultsGrid.appendChild(card);
    });
}

// Volume control
volumeSlider.addEventListener('input', (e) => {
    const volume = e.target.value;
    player.volume = volume;
    // Also update YouTube player volume if active
    if (ytPlayer && typeof ytPlayer.setVolume === 'function') {
        ytPlayer.setVolume(volume * 100); // YouTube uses 0-100
    }
});

// Skip button
skipBtn.addEventListener('click', () => {
    playNext();
});

// Clear playlist
clearPlaylistBtn.addEventListener('click', () => {
    if (confirm('Are you sure you want to clear the playlist?')) {
        playlist = [];
        currentIndex = -1;
        player.pause();
        player.removeAttribute('src');
        if (ytPlayer && typeof ytPlayer.stopVideo === 'function') {
            ytPlayer.stopVideo();
        }
        nowPlayingTitle.innerText = 'No song playing';
        clearLyrics();
        renderPlaylist();
    }
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Prevent shortcuts when typing in search input
    if (document.activeElement === searchInput) return;

    switch (e.code) {
        case 'Space':
            e.preventDefault();
            if (player.paused) player.play();
            else player.pause();
            break;
        case 'ArrowRight':
            player.currentTime += 5;
            break;
        case 'ArrowLeft':
            player.currentTime -= 5;
            break;
        case 'KeyN':
            if (e.ctrlKey) playNext();
            break;
    }
});

function addToPlaylist(item) {
    playlist.push(item);
    renderPlaylist();
    if (currentIndex === -1) {
        playSong(0);
    }
}

function renderPlaylist() {
    if (playlist.length === 0) {
        playlistItems.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding-top: 20px;">No songs in playlist</p>';
        return;
    }

    playlistItems.innerHTML = '';
    playlist.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = `playlist-item ${index === currentIndex ? 'active' : ''}`;
        div.id = `playlist-item-${index}`;
        div.setAttribute('draggable', 'true');
        div.setAttribute('data-index', index);

        div.innerHTML = `
      <img src="${item.thumbnail}" alt="${item.title}" draggable="false">
      <div class="info">
        <div class="title">${item.title}</div>
      </div>
      <div class="delete-btn" title="Remove from playlist">
        <i class="fas fa-times"></i>
      </div>
    `;

        // Click to play
        div.addEventListener('click', (e) => {
            if (e.target.closest('.delete-btn')) return;
            playSong(index);
        });

        // Individual deletion
        const deleteBtn = div.querySelector('.delete-btn');
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            removeFromPlaylist(index);
        });

        // Drag events
        div.addEventListener('dragstart', handleDragStart);
        div.addEventListener('dragover', handleDragOver);
        div.addEventListener('drop', handleDrop);
        div.addEventListener('dragend', handleDragEnd);

        playlistItems.appendChild(div);
    });

    // Auto scroll to active item
    if (currentIndex !== -1) {
        const activeItem = document.getElementById(`playlist-item-${currentIndex}`);
        if (activeItem) {
            activeItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }
}

let draggedItemIndex = null;

function handleDragStart(e) {
    draggedItemIndex = parseInt(this.getAttribute('data-index'));
    this.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
}

function handleDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
}

function handleDrop(e) {
    e.preventDefault();
    const targetIndex = parseInt(this.getAttribute('data-index'));
    if (draggedItemIndex === null || draggedItemIndex === targetIndex) return;

    // Move item in array
    const item = playlist.splice(draggedItemIndex, 1)[0];
    playlist.splice(targetIndex, 0, item);

    // Update currentIndex if it was moved
    if (currentIndex === draggedItemIndex) {
        currentIndex = targetIndex;
    } else if (currentIndex > draggedItemIndex && currentIndex <= targetIndex) {
        currentIndex--;
    } else if (currentIndex < draggedItemIndex && currentIndex >= targetIndex) {
        currentIndex++;
    }

    renderPlaylist();
}

function handleDragEnd() {
    this.classList.remove('dragging');
    draggedItemIndex = null;
}

function removeFromPlaylist(index) {
    const isPlaying = (index === currentIndex);
    playlist.splice(index, 1);

    if (playlist.length === 0) {
        currentIndex = -1;
        player.pause();
        player.removeAttribute('src');
        nowPlayingTitle.innerText = 'No song playing';
    } else {
        if (isPlaying) {
            // If we deleted the playing song, play the same index (now next song)
            playSong(Math.min(index, playlist.length - 1));
        } else if (index < currentIndex) {
            // If we deleted a song before current, shift index
            currentIndex--;
        }
    }
    renderPlaylist();
}

async function playSong(index) {
    if (index < 0 || index >= playlist.length) return;

    const thisRequestId = ++playRequestId;
    currentIndex = index;
    const item = playlist[index];
    nowPlayingTitle.innerText = `Now Playing: ${item.title}`;
    renderPlaylist();

    // Load lyrics for this video (pass title to speed up search)
    loadLyrics(item.id, item.title);

    logDebug(`Loading song: ${item.title}`);

    // Use YouTube IFrame player (more reliable due to YouTube API restrictions)
    if (useYouTubePlayer) {
        try {
            // Show YouTube player, hide HTML5 player
            player.style.display = 'none';
            player.pause();
            player.removeAttribute('src');
            youtubePlayerContainer.style.display = 'block';

            // Wait for YouTube API to be ready
            if (!ytPlayerReady) {
                logDebug('Waiting for YouTube API...');
                await new Promise(resolve => {
                    const checkReady = setInterval(() => {
                        if (ytPlayerReady || typeof YT !== 'undefined' && YT.Player) {
                            ytPlayerReady = true;
                            clearInterval(checkReady);
                            resolve();
                        }
                    }, 100);
                    setTimeout(() => {
                        clearInterval(checkReady);
                        resolve();
                    }, 5000);
                });
            }

            if (thisRequestId !== playRequestId) return;

            await initYouTubePlayer(item.id);
            logDebug('YouTube playback started');

        } catch (err) {
            logDebug(`YouTube player error: ${err.message}, falling back to proxy...`);
            // Fall back to proxy method
            useYouTubePlayer = false;
            await playSongWithProxy(item, thisRequestId);
        }
    } else {
        await playSongWithProxy(item, thisRequestId);
    }
}

async function playSongWithProxy(item, thisRequestId) {
    // Reset player state completely
    youtubePlayerContainer.style.display = 'none';
    if (ytPlayer) {
        ytPlayer.stopVideo();
    }
    player.style.display = 'block';
    player.pause();
    player.removeAttribute('src');
    player.load();

    try {
        const streamUrl = await API.getStreamUrl(item.id);
        if (thisRequestId !== playRequestId) return; // Ignore if another song was requested while resolving

        if (!streamUrl) {
            throw new Error('Server returned empty URL');
        }

        logDebug(`Got URL: ${streamUrl.substring(0, 50)}...`);

        player.src = streamUrl;

        if (audioCtx && audioCtx.state === 'suspended') {
            audioCtx.resume();
        }

        await player.play().catch(e => {
            if (e.name === 'AbortError') {
                logDebug(`Playback aborted (AbortError) - new load request, ignoring.`);
                return;
            }
            logDebug(`Playback failed: ${e.name}`);
            throw e;
        });

        logDebug(`Playback started successfully`);

    } catch (err) {
        // If server told us proxy is unavailable, switch silently to YouTube embed
        const isProxyUnavailable = err.proxy_unavailable ||
            err.message === 'proxy_unavailable' ||
            err.message.includes('proxy_unavailable') ||
            err.message.includes('503');

        if (isProxyUnavailable) {
            logDebug('Proxy unavailable on server - switching to YouTube embed silently');
        } else {
            logDebug(`Proxy failed: ${err.message} - switching to YouTube embed`);
            console.error('Proxy Error:', err);
        }

        // Automatically switch back to YouTube player and retry
        useYouTubePlayer = true;
        updatePlayerModeUI();

        // Show a non-blocking notification only for unexpected failures
        if (!isProxyUnavailable) {
            const notification = document.createElement('div');
            notification.style.cssText = 'position:fixed;top:20px;right:20px;background:#ef4444;color:white;padding:15px 20px;border-radius:10px;box-shadow:0 4px 12px rgba(0,0,0,0.3);z-index:10000;max-width:300px;';
            notification.innerHTML = `
                <strong>&#9888;&#65039; Karaoke Mode Unavailable</strong><br>
                <small>Switched to YouTube mode. Vocal removal won't work due to streaming restrictions.</small>
            `;
            document.body.appendChild(notification);
            setTimeout(() => {
                notification.style.transition = 'opacity 0.5s';
                notification.style.opacity = '0';
                setTimeout(() => notification.remove(), 500);
            }, 5000);
        }

        // Retry with YouTube embed
        if (thisRequestId === playRequestId) {
            await playSong(currentIndex);
        }
    }
}

function playNext() {
    if (currentIndex + 1 < playlist.length) {
        playSong(currentIndex + 1);
    } else {
        // If we've reached the end, stay at the current index but stop
        currentIndex = playlist.length - 1;
    }
}

player.onended = () => {
    playNext();
};

player.onplay = () => {
    try {
        initAudio();
    } catch (e) {
        console.warn("Web Audio Init failed (possibly CORS):", e);
    }

    // Resume context on every play due to browser policies
    if (audioCtx && audioCtx.state === 'suspended') {
        audioCtx.resume().then(() => console.log("AudioContext resumed"));
    }
};

player.onerror = () => {
    const err = player.error;
    let msg = 'Video playback error.';
    let codeName = 'UNKNOWN';
    if (err) {
        switch (err.code) {
            case 1: msg += ' (User aborted)'; codeName = 'MEDIA_ERR_ABORTED'; break;
            case 2: msg += ' (Network error)'; codeName = 'MEDIA_ERR_NETWORK'; break;
            case 3: msg += ' (Decode error - browser may not support this format)'; codeName = 'MEDIA_ERR_DECODE'; break;
            case 4: msg += ' (Unsupported source or format)'; codeName = 'MEDIA_ERR_SRC_NOT_SUPPORTED'; break;
        }
    }
    logDebug(`Player error: [${codeName}] ${msg}`);
    // Do NOT alert here - the playSongWithProxy catch block handles fallback and user messaging.
};

const updateModeUI = (isSinging) => {
    if (isSinging) {
        karaokeKnob.classList.add('active');
        labelSinging.classList.add('active');
        labelGuide.classList.remove('active');
    } else {
        karaokeKnob.classList.remove('active');
        labelSinging.classList.remove('active');
        labelGuide.classList.add('active');
    }
};

karaokeKnob.addEventListener('click', () => {
    const isSinging = !karaokeKnob.classList.contains('active');
    updateModeUI(isSinging);

    if (!audioCtx) return;

    if (isSinging) {
        // Crossfade to wet (Singing Mode - No vocals)
        dryGain.gain.setTargetAtTime(0, audioCtx.currentTime, 0.1);
        wetGain.gain.setTargetAtTime(1, audioCtx.currentTime, 0.1);
    } else {
        // Crossfade back to dry (Guide Mode - With vocals)
        dryGain.gain.setTargetAtTime(1, audioCtx.currentTime, 0.1);
        wetGain.gain.setTargetAtTime(0, audioCtx.currentTime, 0.1);
    }
});

// Export/Import Playlist
const formatDateTime = () => {
    const now = new Date();
    const Y = now.getFullYear();
    const M = String(now.getMonth() + 1).padStart(2, '0');
    const D = String(now.getDate()).padStart(2, '0');
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    const s = String(now.getSeconds()).padStart(2, '0');
    return `${Y}${M}${D}_${h}${m}${s}`;
};

exportBtn.addEventListener('click', () => {
    if (playlist.length === 0) return alert('No songs in playlist to export.');
    const data = JSON.stringify(playlist, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `karaoke-master_playlist_${formatDateTime()}.json`;
    a.click();
    URL.revokeObjectURL(url);
});

importBtn.addEventListener('click', () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (e) => {
            const raw = e.target.result;
            console.log("Raw import content:", raw);
            try {
                const imported = JSON.parse(raw.trim());
                console.log("Imported data:", imported);
                if (Array.isArray(imported)) {
                    playlist = [...playlist, ...imported];
                    renderPlaylist();
                    if (currentIndex === -1 && playlist.length > 0) {
                        playSong(0);
                    }
                    alert('Import successful! Added ' + imported.length + ' songs.');
                } else {
                    throw new Error("Import content is not a valid playlist format (must be an array)");
                }
            } catch (err) {
                console.error("Import error details:", err);
                alert('Import failed:\n' + err.message + '\n\nThe file may be corrupted or incompatible.');
            }
        };
        // Explicitly use UTF-8 just in case
        reader.readAsText(file, 'UTF-8');
    };
    input.click();
});

// Allow enter key to search
searchInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        searchBtn.click();
    }
});
