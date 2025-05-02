// Global state
const state = {
  currentPlaylist: [],
  currentSongIndex: -1,
  isPlaying: false,
  isShuffle: false,
  isRepeat: false,
  isLoggedIn: false,
  userPlaylists: [],
  recentSongs: [],
  likedSongs: [],
  isPlayerExpanded: false
};

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function() {
  updateGreeting();
  initTabs();
  checkAuthStatus();
  loadPublicTracks();
  setupMobileSearch();
  setupProfileDropdown();
  initAudioPlayer();
  setupMobilePlayerControls();
  setupMobileMenu();
});

// ======================== MOBILE PLAYER CONTROLS ========================
function setupMobilePlayerControls() {
  // Mobile play/pause button
  const mobilePlayBtn = document.getElementById('mobile-play-btn');
  if (mobilePlayBtn) {
    mobilePlayBtn.addEventListener('click', togglePlayPause);
  }

  // Mobile skip button
  const mobileSkipBtn = document.getElementById('mobile-skip-btn');
  if (mobileSkipBtn) {
    mobileSkipBtn.addEventListener('click', nextSong);
  }

  // Toggle player expansion
  const nowPlayingBar = document.getElementById('now-playing-bar');
  if (nowPlayingBar) {
    nowPlayingBar.addEventListener('click', function(e) {
      // Don't expand if clicking on play/skip buttons
      if (!e.target.closest('.mobile-play-btn') && !e.target.closest('.mobile-skip-btn')) {
        expandPlayer();
      }
    });
  }

  // Minimize player
  const minimizeBtn = document.getElementById('minimize-player');
  if (minimizeBtn) {
    minimizeBtn.addEventListener('click', minimizePlayer);
  }

  // Expanded player controls
  document.getElementById('play-pause-expanded')?.addEventListener('click', togglePlayPause);
  document.getElementById('next-expanded')?.addEventListener('click', nextSong);
  document.getElementById('prev-expanded')?.addEventListener('click', prevSong);
  document.getElementById('shuffle-expanded')?.addEventListener('click', toggleShuffle);
  document.getElementById('repeat-expanded')?.addEventListener('click', toggleRepeat);
  document.getElementById('like-expanded')?.addEventListener('click', toggleLike);
}

function expandPlayer() {
  const playerExpanded = document.getElementById('player-expanded');
  const playerOverlay = document.getElementById('player-overlay');
  
  if (!playerExpanded || !playerOverlay) return;
  
  state.isPlayerExpanded = true;
  playerExpanded.classList.add('active');
  playerOverlay.classList.add('active');
  
  // Update expanded player with current song info
  updateExpandedPlayer();
  
  // Prevent body scrolling when player is expanded
  document.body.style.overflow = 'hidden';
}

function minimizePlayer() {
  const playerExpanded = document.getElementById('player-expanded');
  const playerOverlay = document.getElementById('player-overlay');
  
  if (!playerExpanded || !playerOverlay) return;
  
  state.isPlayerExpanded = false;
  playerExpanded.classList.remove('active');
  playerOverlay.classList.remove('active');
  
  // Restore body scrolling
  document.body.style.overflow = '';
}

function updateExpandedPlayer() {
  const currentSong = state.currentPlaylist[state.currentSongIndex];
  if (!currentSong) return;

  const albumArt = document.getElementById('expanded-album-art');
  const songTitle = document.getElementById('expanded-song-title');
  const artistName = document.getElementById('expanded-song-artist');
  
  if (albumArt) {
    albumArt.src = currentSong.cover_url || '/public/thumbs/default.jpg';
    albumArt.onerror = function() {
      this.src = '/public/thumbs/default.jpg';
    };
  }
  
  if (songTitle) songTitle.textContent = currentSong.title || 'Untitled';
  if (artistName) artistName.textContent = currentSong.artist || 'Unknown Artist';
  
  // Update play/pause button
  const playPauseBtn = document.getElementById('play-pause-expanded');
  if (playPauseBtn) {
    playPauseBtn.innerHTML = state.isPlaying ? '<i class="fas fa-pause"></i>' : '<i class="fas fa-play"></i>';
  }
  
  // Update shuffle/repeat buttons
  document.getElementById('shuffle-expanded')?.classList.toggle('active', state.isShuffle);
  document.getElementById('repeat-expanded')?.classList.toggle('active', state.isRepeat);
  
  // Update like button
  updateLikeButton(currentSong.id);
}

function updateLikeButton(songId) {
  const likeBtn = document.getElementById('like-expanded');
  const likeIcon = likeBtn?.querySelector('i');
  
  if (!likeBtn || !likeIcon) return;
  
  // Check if song is liked
  const isLiked = state.likedSongs.some(song => song.id === songId);
  
  likeBtn.classList.toggle('liked', isLiked);
  likeIcon.className = isLiked ? 'fas fa-thumbs-up' : 'far fa-thumbs-up';
}

// ======================== MOBILE SEARCH ========================
function setupMobileSearch() {
  const searchBtn = document.getElementById('mobile-search-btn');
  const searchClose = document.getElementById('mobile-search-close');
  const searchContainer = document.getElementById('mobile-search-container');
  const searchInput = document.getElementById('mobile-search-input');
  
  if (!searchBtn || !searchClose || !searchContainer) return;
  
  // Toggle search container visibility
  searchBtn.addEventListener('click', function() {
    searchContainer.classList.toggle('active');
    if (searchContainer.classList.contains('active')) {
      setTimeout(() => searchInput.focus(), 100);
    }
  });
  
  // Close search
  searchClose.addEventListener('click', function() {
    searchContainer.classList.remove('active');
  });
  
  // Handle search form submission
  const mobileSearchForm = document.getElementById('mobile-search-form');
  if (mobileSearchForm) {
    mobileSearchForm.addEventListener('submit', function(e) {
      e.preventDefault();
      const query = searchInput.value.trim().toLowerCase();
      if (query) {
        performSearch(query);
      }
      searchContainer.classList.remove('active');
    });
  }
  
  // Close search when clicking outside
  document.addEventListener('click', function(e) {
    if (!searchBtn.contains(e.target) && 
        !searchContainer.contains(e.target)) {
      searchContainer.classList.remove('active');
    }
  });
}

function performSearch(query) {
  const allCards = document.querySelectorAll(".playlist-card");
  let hasResults = false;
  
  allCards.forEach(card => {
    const title = card.querySelector("h3")?.textContent.toLowerCase() || '';
    const artist = card.querySelector("p")?.textContent.toLowerCase() || '';
    const matches = title.includes(query) || artist.includes(query);
    
    card.style.display = matches ? "block" : "none";
    if (matches) hasResults = true;
  });
  
  // Show message if no results
  const noResultsMsg = document.getElementById('no-results-message');
  if (!hasResults) {
    if (!noResultsMsg) {
      const container = document.querySelector('.playlist-container');
      if (container) {
        container.innerHTML = `
          <div id="no-results-message" class="no-results">
            <i class="fas fa-search"></i>
            <p>No songs found for "${query}"</p>
          </div>
        `;
      }
    }
  } else if (noResultsMsg) {
    noResultsMsg.remove();
  }
}

// ======================== MOBILE MENU ========================
function setupMobileMenu() {
  const menuBtn = document.getElementById('mobile-menu-btn');
  const menuClose = document.getElementById('mobile-menu-close');
  const menuContent = document.getElementById('mobile-menu-content');
  
  if (!menuBtn || !menuClose || !menuContent) return;
  
  // Open menu
  menuBtn.addEventListener('click', function() {
    menuContent.classList.add('active');
  });
  
  // Close menu
  menuClose.addEventListener('click', function() {
    menuContent.classList.remove('active');
  });
  
  // Close menu when clicking outside
  document.addEventListener('click', function(e) {
    if (!menuBtn.contains(e.target) && !menuContent.contains(e.target)) {
      menuContent.classList.remove('active');
    }
  });
  
  // Menu navigation
  menuContent.querySelectorAll('a[data-tab]').forEach(item => {
    item.addEventListener('click', function() {
      const tab = this.getAttribute('data-tab');
      if (tab) {
        document.querySelector(`.tab-button[data-tab="${tab}"]`)?.click();
      }
      menuContent.classList.remove('active');
    });
  });
}

// ======================== CORE FUNCTIONS ========================
function initAudioPlayer() {
  const audioPlayer = document.getElementById("audio-player");
  if (!audioPlayer) return;

  // Audio events
  audioPlayer.addEventListener('ended', handleSongEnded);
  audioPlayer.addEventListener('timeupdate', updateProgressBar);
  audioPlayer.addEventListener('loadedmetadata', updateDurationDisplay);
  
  // Set initial volume
  audioPlayer.volume = 0.7;
}

function getRandomSongs(songs, count) {
  if (!songs || !songs.length) return [];
  
  // Create a copy of the array to avoid mutating the original
  const shuffled = [...songs];
  // Fisher-Yates shuffle algorithm
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled.slice(0, Math.min(count, shuffled.length));
}

async function addToHistory(songId) {
  try {
    const response = await fetch('/api/history/add', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ song_id: songId }),
      credentials: 'include'
    });
    
    if (!response.ok) throw new Error('Failed to add to history');
    
    // Update recent songs in state
    const song = state.currentPlaylist.find(s => s.id == songId);
    if (song) {
      state.recentSongs = [song, ...state.recentSongs.filter(s => s.id != songId)];
      renderSongsToContainer(state.recentSongs, "#recent-songs");
    }
  } catch (error) {
    console.error("Error adding to history:", error);
  }
}

async function loadPublicTracks() {
  try {
    showLoader();
    
    const response = await fetch('/api/player/songs');
    if (!response.ok) throw new Error('Failed to load songs');
    
    const songs = await response.json();
    if (!Array.isArray(songs)) throw new Error('Invalid songs data');
    
    state.currentPlaylist = songs;
    
    // Show 12 random recommended songs for first-time visitors
    const recommendedContainer = document.querySelector("#recommended-songs");
    if (recommendedContainer) {
      if (!localStorage.getItem('hasVisitedBefore') && songs.length > 0) {
        const recommendedSongs = getRandomSongs(songs, 12);
        renderSongsToContainer(recommendedSongs, "#recommended-songs");
        localStorage.setItem('hasVisitedBefore', 'true');
      } else {
        // Show placeholder for returning visitors
        recommendedContainer.innerHTML = `
          <div class="section-placeholder">
            <i class="fas fa-home"></i>
            <p>Welcome back! Browse our music collection</p>
          </div>
        `;
      }
    }
    
    // Render all songs in the "All Songs" tab (random order)
    const allSongsRandom = getRandomSongs(songs, songs.length);
    renderSongsToContainer(allSongsRandom, "#all-songs");
    
    // Render trending songs with random songs
    renderSongsToContainer(getRandomSongs(songs, 12), "#trending-songs");
    
    hideLoader();
    
  } catch (error) {
    console.error("Error loading songs:", error);
    showError("Failed to load songs. Please try again later.");
  }
}

function renderSongsToContainer(songs, containerSelector) {
  const container = document.querySelector(containerSelector);
  if (!container) {
    console.error(`Container not found: ${containerSelector}`);
    return;
  }
  
  if (!songs || !songs.length) {
    container.innerHTML = '<div class="no-songs">No songs found</div>';
    return;
  }
  
  container.innerHTML = songs.map(song => `
    <div class="playlist-card" data-song-id="${song.id}">
      <div class="playlist-image-container">
        <img src="${song.cover_url || '/public/thumbs/default.jpg'}" 
             alt="${song.title}" 
             onerror="this.src='/public/thumbs/default.jpg'" loading="lazy">
        <button class="play-button">
          <i class="fas fa-play"></i>
        </button>
      </div>
      <div class="playlist-info">
        <h3>${song.title || 'Untitled'}</h3>
        <p>${song.artist || 'Unknown Artist'}</p>
      </div>
    </div>
  `).join('');
  
  // Add click events
  container.querySelectorAll('.playlist-card').forEach(card => {
    const songId = card.dataset.songId;
    const song = state.currentPlaylist.find(s => s.id == songId) || 
                state.recentSongs.find(s => s.id == songId) ||
                state.likedSongs.find(s => s.id == songId);
    if (!song) return;

    // Play button click
    const playBtn = card.querySelector('.play-button');
    playBtn?.addEventListener('click', function(e) {
      e.stopPropagation();
      playSong(song);
    });
    
    // Whole card click
    card.addEventListener('click', function(e) {
      if (!e.target.closest('button')) {
        playSong(song);
      }
    });
  });
}

function playSong(song) {
  // Redirect to login if not logged in
  if (!state.isLoggedIn) {
    window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
    return;
  }

  const audioPlayer = document.getElementById("audio-player");
  const nowPlayingBar = document.getElementById("now-playing-bar");
  const nowPlayingCover = document.getElementById("mobile-song-image");
  
  if (!audioPlayer || !song || !song.audio_url) {
    console.error("Cannot play song - missing required elements");
    return;
  }
  
  try {
    // Update state
    state.currentSongIndex = state.currentPlaylist.findIndex(s => s.id === song.id);
    state.isPlaying = true;
    
    // Update UI
    nowPlayingBar?.classList.remove("hidden");
    if (nowPlayingCover) {
      nowPlayingCover.src = song.cover_url || '/public/thumbs/default.jpg';
      nowPlayingCover.onerror = function() {
        this.src = '/public/thumbs/default.jpg';
      };
    }
    
    const titleElement = document.querySelector(".now-playing-title");
    const artistElement = document.querySelector(".now-playing-artist");
    if (titleElement) titleElement.textContent = song.title || 'Untitled';
    if (artistElement) artistElement.textContent = song.artist || 'Unknown Artist';
    
    // Update play button
    const mobilePlayIcon = document.querySelector('#mobile-play-btn i');
    if (mobilePlayIcon) mobilePlayIcon.className = 'fas fa-pause';
    
    // Update expanded player if visible
    if (state.isPlayerExpanded) {
      updateExpandedPlayer();
    }
    
    // Set audio source and play
    audioPlayer.src = song.audio_url;
    audioPlayer.load(); // Ensure audio is loaded
    audioPlayer.play().catch(e => {
      console.error("Playback error:", e);
      showError("Could not play the song");
      nowPlayingBar?.classList.add("hidden");
      if (mobilePlayIcon) mobilePlayIcon.className = 'fas fa-play';
      state.isPlaying = false;
    });

    // Add to recent history if logged in
    if (state.isLoggedIn) {
      addToHistory(song.id);
    }
  } catch (error) {
    console.error("Error playing song:", error);
    showError("Error playing song");
  }
}

// ======================== PLAYER CONTROLS ========================
function togglePlayPause() {
  const audioPlayer = document.getElementById("audio-player");
  const nowPlayingBar = document.getElementById("now-playing-bar");
  const mobilePlayIcon = document.querySelector('#mobile-play-btn i');
  const expandedPlayIcon = document.querySelector('#play-pause-expanded i');
  
  if (!audioPlayer.src || state.currentSongIndex === -1) return;

  if (audioPlayer.paused) {
    audioPlayer.play()
      .then(() => {
        nowPlayingBar?.classList.remove("hidden");
        if (mobilePlayIcon) mobilePlayIcon.className = 'fas fa-pause';
        if (expandedPlayIcon) expandedPlayIcon.className = 'fas fa-pause';
        state.isPlaying = true;
      })
      .catch(e => {
        console.error("Play failed:", e);
        showError("Playback failed: " + e.message);
      });
  } else {
    audioPlayer.pause();
    if (mobilePlayIcon) mobilePlayIcon.className = 'fas fa-play';
    if (expandedPlayIcon) expandedPlayIcon.className = 'fas fa-play';
    state.isPlaying = false;
  }
}

function nextSong() {
  if (state.currentPlaylist.length === 0) return;
  
  let newIndex = state.isShuffle 
    ? Math.floor(Math.random() * state.currentPlaylist.length)
    : (state.currentSongIndex + 1) % state.currentPlaylist.length;
  
  playSong(state.currentPlaylist[newIndex]);
}

function prevSong() {
  if (state.currentPlaylist.length === 0) return;
  
  // If we're more than 3 seconds into the song, restart it
  const audioPlayer = document.getElementById("audio-player");
  if (audioPlayer.currentTime > 3) {
    audioPlayer.currentTime = 0;
    return;
  }
  
  const newIndex = (state.currentSongIndex - 1 + state.currentPlaylist.length) % state.currentPlaylist.length;
  playSong(state.currentPlaylist[newIndex]);
}

function handleSongEnded() {
  if (state.isRepeat) {
    document.getElementById("audio-player").currentTime = 0;
    document.getElementById("audio-player").play();
  } else {
    nextSong();
  }
}

function toggleShuffle() {
  state.isShuffle = !state.isShuffle;
  document.getElementById("shuffle-expanded")?.classList.toggle('active', state.isShuffle);
}

function toggleRepeat() {
  state.isRepeat = !state.isRepeat;
  document.getElementById("repeat-expanded")?.classList.toggle('active', state.isRepeat);
}

async function toggleLike() {
  const songId = state.currentPlaylist[state.currentSongIndex]?.id;
  if (!songId) return;

  const likeBtn = document.getElementById('like-expanded');
  const likeIcon = likeBtn?.querySelector('i');
  
  try {
    const response = await fetch(`/api/user/likes/${songId}`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      credentials: 'include'
    });
    
    if (response.status === 401) {
      window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
      return;
    }
    
    if (!response.ok) throw new Error('Like failed');
    
    // Toggle like state
    const isLiked = likeBtn.classList.contains('liked');
    
    if (isLiked) {
      // Unlike the song
      state.likedSongs = state.likedSongs.filter(song => song.id !== songId);
      likeBtn.classList.remove('liked');
      likeIcon.className = 'far fa-thumbs-up';
    } else {
      // Like the song
      const song = state.currentPlaylist[state.currentSongIndex];
      if (song) {
        state.likedSongs = [song, ...state.likedSongs];
        likeBtn.classList.add('liked');
        likeIcon.className = 'fas fa-thumbs-up';
      }
    }
    
    // Update favorites tab
    renderSongsToContainer(state.likedSongs, "#favorites-songs");
    
    // Animation
    if (likeBtn) {
      likeBtn.style.transform = 'scale(1.2)';
      setTimeout(() => likeBtn.style.transform = 'scale(1)', 300);
    }
  } catch (error) {
    console.error('Error:', error);
    alert('Failed to toggle like: ' + error.message);
  }
}

// ======================== PROGRESS BAR ========================
function updateProgressBar() {
  const audioPlayer = document.getElementById("audio-player");
  const currentTimeExpanded = document.getElementById("current-time-expanded");
  const progressExpanded = document.getElementById("progress-expanded");
  
  if (!audioPlayer.duration) return;
  
  const percent = (audioPlayer.currentTime / audioPlayer.duration) * 100;
  if (progressExpanded) progressExpanded.style.width = `${percent}%`;
  
  const formattedTime = formatTime(audioPlayer.currentTime);
  if (currentTimeExpanded) currentTimeExpanded.textContent = formattedTime;
}

function updateDurationDisplay() {
  const audioPlayer = document.getElementById("audio-player");
  const durationExpanded = document.getElementById("duration-expanded");
  
  if (audioPlayer.duration) {
    const formattedDuration = formatTime(audioPlayer.duration);
    if (durationExpanded) durationExpanded.textContent = formattedDuration;
  }
}

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
}

// Setup progress bar interaction
function setupProgressBarInteraction() {
  const progressBar = document.getElementById("progress-bar-expanded");
  
  if (!progressBar) return;

  progressBar.addEventListener('click', (e) => {
    const audioPlayer = document.getElementById("audio-player");
    const rect = progressBar.getBoundingClientRect();
    const percent = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    document.getElementById("progress-expanded").style.width = `${percent * 100}%`;
    audioPlayer.currentTime = percent * audioPlayer.duration;
  });
}

// ======================== TABS ========================
function initTabs() {
  const tabButtons = document.querySelectorAll(".tab-button");
  const tabContents = document.querySelectorAll(".tab-content");
  
  tabButtons.forEach(button => {
    button.addEventListener("click", () => {
      tabButtons.forEach(btn => btn.classList.remove("active"));
      tabContents.forEach(content => content.classList.remove("active"));
      button.classList.add("active");
      document.getElementById(`${button.dataset.tab}-tab`).classList.add("active");
    });
  });
}

// ======================== AUTH FUNCTIONS ========================
async function checkAuthStatus() {
  try {
    const response = await fetch('/api/auth/status', {credentials: 'include'});
    if (response.ok) {
      const data = await response.json();
      state.isLoggedIn = data.isLoggedIn;
      updateAuthUI(data.isLoggedIn, data.user);
    }
  } catch (error) {
    console.error("Auth check error:", error);
  }
}

function updateAuthUI(isLoggedIn, userData = null) {
  const mobileAuthSection = document.getElementById("mobile-auth-section");
  const profileDropdown = document.querySelector(".profile-dropdown");
  
  if (isLoggedIn && userData) {
    // Update mobile auth section
    if (mobileAuthSection) {
      mobileAuthSection.innerHTML = `
        <a href="/my-account"><i class="fas fa-user"></i> My Account</a>
        <a href="/logout"><i class="fas fa-sign-out-alt"></i> Logout</a>
      `;
    }
    
    // Update profile image
    const profileImg = document.getElementById("mobile-profile-avatar");
    if (profileImg && userData.profile_image) {
      profileImg.src = userData.profile_image;
    }
    
    // Show profile dropdown
    if (profileDropdown) {
      profileDropdown.style.display = 'block';
    }
  } else {
    // Show login/signup buttons
    if (mobileAuthSection) {
      mobileAuthSection.innerHTML = `
        <a href="/login" class="mobile-login-btn"><i class="fas fa-sign-in-alt"></i> Sign In</a>
        <a href="/register" class="mobile-signup-btn"><i class="fas fa-user-plus"></i> Sign Up</a>
      `;
    }
    
    // Hide profile dropdown
    if (profileDropdown) {
      profileDropdown.style.display = 'none';
    }
  }
}

function setupProfileDropdown() {
  const profileButton = document.getElementById("profile-button");
  if (!profileButton) return;
  
  profileButton.addEventListener("click", function(e) {
    e.stopPropagation();
    const dropdown = document.getElementById("dropdown-content");
    dropdown.style.display = dropdown.style.display === "block" ? "none" : "block";
  });
  
  document.addEventListener("click", function() {
    document.getElementById("dropdown-content").style.display = "none";
  });
  
  document.getElementById("logout-btn")?.addEventListener("click", async function(e) {
    e.preventDefault();
    try {
      await fetch('/api/auth/logout', {method: 'POST', credentials: 'include'});
      window.location.href = "/";
    } catch (error) {
      console.error("Logout error:", error);
    }
  });
}

// ======================== UTILITY FUNCTIONS ========================
function updateGreeting() {
  const hour = new Date().getHours();
  const greeting = document.getElementById('greeting-text');
  greeting.textContent = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
}

function showLoader() {
  const containers = document.querySelectorAll(".playlist-container");
  if (!containers.length) return;
  
  containers.forEach(container => {
    container.innerHTML = '<div class="loader"><i class="fas fa-spinner fa-spin"></i> Loading...</div>';
  });
}

function hideLoader() {
  // Implement any loader hiding logic if needed
}

function showError(message) {
  const containers = document.querySelectorAll(".playlist-container");
  if (!containers.length) return;
  
  containers.forEach(container => {
    container.innerHTML = `
      <div class="error-message">
        <i class="fas fa-exclamation-circle"></i>
        <p>${message}</p>
        <button onclick="location.reload()">Try Again</button>
      </div>
    `;
  });
}

// Initialize progress bar interaction
setupProgressBarInteraction();