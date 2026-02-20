const player = document.getElementById('player');
const searchInput = document.getElementById('search-input');
const searchBtn = document.getElementById('search-btn');
const resultsSection = document.getElementById('results-section');
const resultsGrid = document.getElementById('results-grid');
const loader = document.getElementById('search-loader');
const playlistItems = document.getElementById('playlist-items');
const nowPlayingTitle = document.getElementById('now-playing-title');
const karaokeKnob = document.getElementById('karaoke-knob');
const labelGuide = document.getElementById('label-guide');
const labelSinging = document.getElementById('label-singing');

const exportBtn = document.getElementById('export-playlist-btn');
const importBtn = document.getElementById('import-playlist-btn');

const skipBtn = document.getElementById('skip-btn');
const volumeSlider = document.getElementById('volume-slider');
const clearPlaylistBtn = document.getElementById('clear-playlist-btn');

let playlist = [];
let currentIndex = -1;
let playRequestId = 0;

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
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Failed to get stream URL');
            }
            const data = await response.json();
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
        alert('請輸入歌詞');
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
            alert('儲存失敗: ' + (data.error || 'Unknown error'));
        }
    } catch (err) {
        console.error('Save lyrics error:', err);
        alert('儲存失敗: ' + err.message);
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
            label = '💾 已儲存';
        } else if (source.includes('netease')) {
            label = '🎵 網易';
        } else if (source.includes('kugou')) {
            label = '🎵 酷狗';
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
    if (lyricsContent) lyricsContent.innerHTML = '<div class="lyrics-loading">搜尋歌詞中...</div>';
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
                    🎵 找不到此歌曲的歌詞<br>
                    <small>點擊「編輯」按鈕手動新增歌詞</small>
                </p>`;
            return;
        }

        currentLyricsText = data.lyrics;
        renderLyrics();
        
        logDebug(`Loaded lyrics from ${data.source}`);

    } catch (err) {
        console.error('Failed to load lyrics:', err);
        if (lyricsContent) lyricsContent.innerHTML = '<p class="lyrics-unavailable">載入歌詞失敗</p>';
    }
}

// Render lyrics as simple scrollable text
function renderLyrics() {
    if (!lyricsContent) return;
    
    if (!currentLyricsText) {
        lyricsContent.innerHTML = '<p class="lyrics-placeholder">🎤 歌詞將在播放時顯示</p>';
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
    if (lyricsContent) lyricsContent.innerHTML = '<p class="lyrics-placeholder">🎤 歌詞將在播放時顯示</p>';
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
                alert('無法獲取影片資訊，請檢查網址是否正確。');
            }
        } else {
            // Search keyword
            const results = await API.searchYouTube(query);
            if (results && results.length > 0) {
                displayResults(results);
            } else {
                alert('找不到相關結果，請換個關鍵字搜尋。');
            }
        }
    } catch (err) {
        console.error('API call error:', err);
        alert('搜尋發生系統錯誤：' + err.message);
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
    player.volume = e.target.value;
});

// Skip button
skipBtn.addEventListener('click', () => {
    playNext();
});

// Clear playlist
clearPlaylistBtn.addEventListener('click', () => {
    if (confirm('確定要清空待播清單嗎？')) {
        playlist = [];
        currentIndex = -1;
        player.pause();
        player.removeAttribute('src');
        nowPlayingTitle.innerText = '尚未播放歌曲';
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
        playlistItems.innerHTML = '<p style="text-align: center; color: rgba(255,255,255,0.3); padding-top: 20px;">目前沒有待播歌曲</p>';
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
      <div class="delete-btn" title="從清單移除">
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
        nowPlayingTitle.innerText = '尚未播放歌曲';
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
    nowPlayingTitle.innerText = `正在播放：${item.title}`;
    renderPlaylist();

    // Reset player state completely
    player.pause();
    player.removeAttribute('src');
    player.load();

    // Load lyrics for this video (pass title to speed up search)
    loadLyrics(item.id, item.title);

    logDebug(`正在解析歌曲: ${item.title}`);

    try {
        const streamUrl = await API.getStreamUrl(item.id);
        if (thisRequestId !== playRequestId) return; // Ignore if another song was requested while resolving

        if (!streamUrl) {
            throw new Error('後端回傳網址為空');
        }

        logDebug(`取得網址: ${streamUrl.substring(0, 50)}...`);

        player.src = streamUrl;

        if (audioCtx && audioCtx.state === 'suspended') {
            audioCtx.resume();
        }

        await player.play().catch(e => {
            if (e.name === 'AbortError') {
                logDebug(`播放被中止 (AbortError) - 可能有新的載入請求，忽略此錯誤。`);
                return;
            }
            logDebug(`播放啟動失敗: ${e.name}`);
            throw e;
        });

        logDebug(`開始成功播放`);

    } catch (err) {
        logDebug(`錯誤詳細: ${err.message}`);
        console.error('Playback Context Error:', err);
        alert(`播放失敗：${err.message}\n\n這通常與 YouTube 限制或網路狀況有關。請嘗試搜尋其他版本的影片或稍後再試。`);

        setTimeout(playNext, 3000);
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
    let msg = '影片播放發生錯誤。';
    let codeName = 'UNKNOWN';
    if (err) {
        switch (err.code) {
            case 1: msg += ' (使用者中止)'; codeName = 'MEDIA_ERR_ABORTED'; break;
            case 2: msg += ' (網路錯誤)'; codeName = 'MEDIA_ERR_NETWORK'; break;
            case 3: msg += ' (解碼錯誤 - 瀏覽器可能不支援此格式)'; codeName = 'MEDIA_ERR_DECODE'; break;
            case 4: msg += ' (不支援的來源或格式)'; codeName = 'MEDIA_ERR_SRC_NOT_SUPPORTED'; break;
        }
    }
    logDebug(`播放器報錯: [${codeName}] ${msg}`);
    alert(`播放失敗 (錯誤碼 ${err ? err.code : '?'}): ${msg}\n\n這通常與網路環境或 YouTube 的限制有關。請嘗試搜尋其他影片來源。`);
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
    if (playlist.length === 0) return alert('目前沒有待播歌曲可以匯出。');
    const data = JSON.stringify(playlist, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `karaoke-shen_playlist_${formatDateTime()}.json`;
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
                    alert('匯入成功！已加入 ' + imported.length + ' 首歌曲。');
                } else {
                    throw new Error("匯入內容不是有效的清單格式（必須是陣列）");
                }
            } catch (err) {
                console.error("Import error details:", err);
                alert('匯入失敗：\n' + err.message + '\n\n這可能是檔案內容毀損或格式不相容。');
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
