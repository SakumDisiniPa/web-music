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

  // DOM Elements
  const elements = {
    // Audio
    audioPlayer: document.getElementById('audio-player'),
    
    // Header
    mobileMenuButton: document.querySelector('.mobile-menu-button'),
    mobileMenuContent: document.querySelector('.mobile-menu-content'),
    mobileSearchButton: document.querySelector('.mobile-search-button'),
    mobileSearchContainer: document.querySelector('.mobile-search-container'),
    mobileSearchClose: document.querySelector('.mobile-search-close'),
    
    // Player
    player: document.getElementById('player'),
    playButton: document.getElementById('play-btn'),
    expandedPlayButton: document.getElementById('play-btn-expanded'),
    prevButton: document.getElementById('prev-btn'),
    nextButton: document.getElementById('next-btn'),
    shuffleButton: document.getElementById('shuffle-btn'),
    repeatButton: document.getElementById('repeat-btn'),
    volumeButton: document.getElementById('volume-btn'),
    volumeIcon: document.getElementById('volume-icon'),
    progressBar: document.getElementById('progress-bar'),
    progress: document.getElementById('progress'),
    volumeBar: document.getElementById('volume-bar'),
    volumeProgress: document.getElementById('volume-progress'),
    currentTimeDisplay: document.getElementById('current-time'),
    durationDisplay: document.getElementById('duration'),
    
    // Expanded Player
    playerOverlay: document.querySelector('.player-overlay'),
    playerExpanded: document.getElementById('player-expanded'),
    minimizeButton: document.getElementById('minimize-button'),
    likeButton: document.getElementById('like-button'),
    currentTimeExpanded: document.getElementById('current-time-expanded'),
    durationExpanded: document.getElementById('duration-expanded'),
    progressBarExpanded: document.getElementById('progress-bar-expanded'),
    progressExpanded: document.getElementById('progress-expanded'),
    expandedAlbumArt: document.getElementById('expanded-album-art'),
    expandedSongTitle: document.getElementById('expanded-song-title'),
    expandedSongArtist: document.getElementById('expanded-song-artist'),
    
    // Song Info
    songCover: document.querySelector('.song-cover'),
    songTitle: document.querySelector('.song-title'),
    songArtist: document.querySelector('.song-artist'),
    
    // Tabs
    tabButtons: document.querySelectorAll('.tab-button'),
    tabContents: document.querySelectorAll('.tab-content'),
    
    // Sidebar
    sidebarItems: document.querySelectorAll('.sidebar-item'),
    
    // Playlists
    addPlaylistButton: document.getElementById('add-playlist-btn'),
    playlistModal: document.getElementById('add-playlist-modal'),
    closeModalButton: document.getElementById('close-modal-button'),
    cancelButton: document.getElementById('cancel-button'),
    playlistForm: document.getElementById('playlist-form'),
    
    // Greeting
    greetingText: document.getElementById('greeting-text'),
    
    // Footer
    currentYear: document.getElementById('current-year')
  };

  // Initialize when DOM is loaded
  document.addEventListener('DOMContentLoaded', function() {
    updateGreeting();
    initTabs();
    checkAuthStatus();
    loadPublicTracks();
    setupSearch();
    setupProfileDropdown();
    initAudioPlayer();
    setupVolumeControl();
    setupProgressBar();
    setupSidebarNavigation();
    setupPlaylistModal();
    loadUserPlaylists();
    loadRecentSongs();
    loadLikedSongs();
    updateCurrentYear();
  });

  // ======================== UTILITY FUNCTIONS ========================
  function updateCurrentYear() {
    elements.currentYear.textContent = new Date().getFullYear();
  }

  function updateGreeting() {
    const hour = new Date().getHours();
    elements.greetingText.textContent = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  }

  function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  }

  function showLoader(container) {
    container.innerHTML = `
      <div class="loader">
        <i class="fas fa-spinner loader-spinner"></i>
        <span>Loading...</span>
      </div>
    `;
  }

  function showError(container, message) {
    container.innerHTML = `
      <div class="error-message">
        <i class="fas fa-exclamation-circle error-icon"></i>
        <p class="error-text">${message}</p>
        <button class="retry-button">Try Again</button>
      </div>
    `;
    
    container.querySelector('.retry-button').addEventListener('click', function() {
      window.location.reload();
    });
  }

  function showPlaceholder(container, icon, message) {
    container.innerHTML = `
      <div class="placeholder">
        <i class="fas ${icon} placeholder-icon"></i>
        <p class="placeholder-text">${message}</p>
      </div>
    `;
  }

  // ======================== AUTH FUNCTIONS ========================
  async function checkAuthStatus() {
    try {
      const response = await fetch('/api/auth/status', { credentials: 'include' });
      if (response.ok) {
        const data = await response.json();
        state.isLoggedIn = data.isLoggedIn;
        updateAuthUI(data.isLoggedIn, data.user);
      }
    } catch (error) {
      console.error('Auth check error:', error);
    }
  }

  function updateAuthUI(isLoggedIn, userData = null) {
    const authButtons = document.querySelector('.auth-buttons');
    const profileDropdown = document.querySelector('.profile-dropdown');
    
    if (isLoggedIn && userData) {
      authButtons.style.display = 'none';
      profileDropdown.style.display = 'block';
      
      // Update profile info
      const usernameElement = profileDropdown.querySelector('.username');
      const avatarElement = profileDropdown.querySelector('.profile-avatar');
      
      if (usernameElement) usernameElement.textContent = userData.username || 'User';
      if (avatarElement) avatarElement.src = userData.avatar || '/public/thumbs/default-avatar.jpg';
    } else {
      authButtons.style.display = 'flex';
      profileDropdown.style.display = 'none';
    }
  }

  function setupProfileDropdown() {
    const profileButton = document.querySelector('.profile-button');
    if (!profileButton) return;
    
    profileButton.addEventListener('click', function(e) {
      e.stopPropagation();
      const dropdown = document.querySelector('.dropdown-content');
      dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
    });
    
    document.addEventListener('click', function() {
      document.querySelector('.dropdown-content').style.display = 'none';
    });
    
    document.querySelector('.dropdown-content a[href="/logout"]').addEventListener('click', async function(e) {
      e.preventDefault();
      try {
        await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
        window.location.href = '/';
      } catch (error) {
        console.error('Logout error:', error);
      }
    });
  }

  // ======================== PLAYER FUNCTIONS ========================
  function initAudioPlayer() {
    // Event listeners for audio player
    elements.audioPlayer.addEventListener('timeupdate', updateProgressBar);
    elements.audioPlayer.addEventListener('loadedmetadata', updateDurationDisplay);
    elements.audioPlayer.addEventListener('ended', handleSongEnded);
    elements.audioPlayer.addEventListener('play', () => {
      state.isPlaying = true;
      updatePlayButton();
    });
    elements.audioPlayer.addEventListener('pause', () => {
      state.isPlaying = false;
      updatePlayButton();
    });
    
    // Set initial volume
    elements.audioPlayer.volume = 0.7;
    
    // Play/Pause buttons
    elements.playButton.addEventListener('click', togglePlayPause);
    elements.expandedPlayButton.addEventListener('click', togglePlayPause);
    
    // Navigation buttons
    elements.prevButton.addEventListener('click', prevSong);
    elements.nextButton.addEventListener('click', nextSong);
    
    // Shuffle/Repeat buttons
    elements.shuffleButton.addEventListener('click', toggleShuffle);
    elements.repeatButton.addEventListener('click', toggleRepeat);
    
    // Expanded player buttons
    document.getElementById('prev-btn-expanded').addEventListener('click', prevSong);
    document.getElementById('next-btn-expanded').addEventListener('click', nextSong);
    document.getElementById('shuffle-btn-expanded').addEventListener('click', toggleShuffle);
    document.getElementById('repeat-btn-expanded').addEventListener('click', toggleRepeat);
    
    // Like button
    elements.likeButton.addEventListener('click', toggleLike);
    
    // Minimize button
    elements.minimizeButton.addEventListener('click', minimizePlayer);
    
    // Player click to expand
    elements.player.addEventListener('click', expandPlayer);
  }

  function updatePlayButton() {
    const icon = state.isPlaying ? 'fa-pause' : 'fa-play';
    elements.playButton.innerHTML = `<i class="fas ${icon}"></i>`;
    elements.expandedPlayButton.innerHTML = `<i class="fas ${icon}"></i>`;
  }

  function setupProgressBar() {
    let isDragging = false;
    
    // Desktop progress bar
    elements.progressBar.addEventListener('mousedown', function(e) {
      isDragging = true;
      updateProgress(e);
    });
    
    document.addEventListener('mousemove', function(e) {
      if (isDragging) updateProgress(e);
    });
    
    document.addEventListener('mouseup', function() {
      isDragging = false;
    });
    
    elements.progressBar.addEventListener('click', updateProgress);
    
    // Expanded player progress bar
    elements.progressBarExpanded.addEventListener('click', updateProgress);
    
    function updateProgress(e) {
      const rect = e.currentTarget.getBoundingClientRect();
      const percent = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
      
      // Update progress bars
      elements.progress.style.width = `${percent * 100}%`;
      elements.progressExpanded.style.width = `${percent * 100}%`;
      
      // Update audio time
      elements.audioPlayer.currentTime = percent * elements.audioPlayer.duration;
    }
  }

  function updateProgressBar() {
    if (!elements.audioPlayer.duration) return;
    
    const percent = (elements.audioPlayer.currentTime / elements.audioPlayer.duration) * 100;
    
    // Update progress bars
    elements.progress.style.width = `${percent}%`;
    elements.progressExpanded.style.width = `${percent}%`;
    
    // Update time displays
    const formattedTime = formatTime(elements.audioPlayer.currentTime);
    elements.currentTimeDisplay.textContent = formattedTime;
    elements.currentTimeExpanded.textContent = formattedTime;
  }

  function updateDurationDisplay() {
    if (elements.audioPlayer.duration) {
      const formattedDuration = formatTime(elements.audioPlayer.duration);
      elements.durationDisplay.textContent = formattedDuration;
      elements.durationExpanded.textContent = formattedDuration;
    }
  }

  function setupVolumeControl() {
    let isDragging = false;
    
    elements.volumeBar.addEventListener('mousedown', function(e) {
      isDragging = true;
      updateVolume(e);
    });
    
    document.addEventListener('mousemove', function(e) {
      if (isDragging) updateVolume(e);
    });
    
    document.addEventListener('mouseup', function() {
      isDragging = false;
    });
    
    elements.volumeBar.addEventListener('click', updateVolume);
    
    elements.volumeButton.addEventListener('click', toggleMute);
    
    function updateVolume(e) {
      const rect = elements.volumeBar.getBoundingClientRect();
      const percent = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
      
      // Update volume progress
      elements.volumeProgress.style.width = `${percent * 100}%`;
      
      // Update audio volume
      elements.audioPlayer.volume = percent;
      
      // Update volume icon
      updateVolumeIcon(percent);
    }
    
    function updateVolumeIcon(volume) {
      let icon;
      if (volume === 0) {
        icon = 'fa-volume-mute';
      } else if (volume < 0.5) {
        icon = 'fa-volume-down';
      } else {
        icon = 'fa-volume-up';
      }
      elements.volumeIcon.className = `fas ${icon}`;
    }
    
    function toggleMute() {
      if (elements.audioPlayer.volume > 0) {
        elements.audioPlayer.dataset.lastVolume = elements.audioPlayer.volume;
        elements.audioPlayer.volume = 0;
        elements.volumeProgress.style.width = '0%';
        elements.volumeIcon.className = 'fas fa-volume-mute';
      } else {
        const lastVolume = parseFloat(elements.audioPlayer.dataset.lastVolume) || 0.7;
        elements.audioPlayer.volume = lastVolume;
        elements.volumeProgress.style.width = `${lastVolume * 100}%`;
        updateVolumeIcon(lastVolume);
      }
    }
  }

  function playSong(song) {
    if (!song || !song.audio_url) return;
    
    // Update state
    state.currentSongIndex = state.currentPlaylist.findIndex(s => s.id === song.id);
    
    // Update UI
    elements.player.classList.remove('hidden');
    
    // Update song info
    updateSongInfo(song);
    
    // Set audio source and play
    elements.audioPlayer.src = song.audio_url;
    elements.audioPlayer.play().catch(error => {
      console.error('Playback error:', error);
      showError(document.createElement('div'), 'Could not play the song');
    });
    
    // Add to recent history if logged in
    if (state.isLoggedIn) {
      addToHistory(song.id);
    }
  }

  function updateSongInfo(song) {
    // Update covers
    elements.songCover.src = song.cover_url || '/public/thumbs/default.jpg';
    elements.expandedAlbumArt.src = song.cover_url || '/public/thumbs/default.jpg;'
    
    // Update titles
    elements.songTitle.textContent = song.title || 'Untitled';
    elements.expandedSongTitle.textContent = song.title || 'Untitled';
    
    // Update artists
    elements.songArtist.textContent = song.artist || 'Unknown Artist';
    elements.expandedSongArtist.textContent = song.artist || 'Unknown Artist';
    
    // Update like button
    updateLikeButton(song.id);
  }

  function togglePlayPause() {
    if (!elements.audioPlayer.src) return;
    
    if (elements.audioPlayer.paused) {
      elements.audioPlayer.play().catch(error => {
        console.error('Play error:', error);
      });
    } else {
      elements.audioPlayer.pause();
    }
  }

  function prevSong() {
    if (state.currentPlaylist.length === 0) return;
    
    // If we're more than 3 seconds into the song, restart it
    if (elements.audioPlayer.currentTime > 3) {
      elements.audioPlayer.currentTime = 0;
      return;
    }
    
    const newIndex = (state.currentSongIndex - 1 + state.currentPlaylist.length) % state.currentPlaylist.length;
    playSong(state.currentPlaylist[newIndex]);
  }

  function nextSong() {
    if (state.currentPlaylist.length === 0) return;
    
    let newIndex;
    if (state.isShuffle) {
      newIndex = Math.floor(Math.random() * state.currentPlaylist.length);
    } else {
      newIndex = (state.currentSongIndex + 1) % state.currentPlaylist.length;
    }
    
    playSong(state.currentPlaylist[newIndex]);
  }

  function handleSongEnded() {
    if (state.isRepeat) {
      elements.audioPlayer.currentTime = 0;
      elements.audioPlayer.play();
    } else {
      nextSong();
    }
  }

  function toggleShuffle() {
    state.isShuffle = !state.isShuffle;
    elements.shuffleButton.classList.toggle('active', state.isShuffle);
    document.getElementById('shuffle-btn-expanded').classList.toggle('active', state.isShuffle);
  }

  function toggleRepeat() {
    state.isRepeat = !state.isRepeat;
    elements.repeatButton.classList.toggle('active', state.isRepeat);
    document.getElementById('repeat-btn-expanded').classList.toggle('active', state.isRepeat);
  }

  async function toggleLike() {
    const songId = state.currentPlaylist[state.currentSongIndex]?.id;
    if (!songId) return;
    
    try {
      const response = await fetch(`/api/user/likes/${songId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include'
      });
      
      if (response.status === 401) {
        window.location.href = '/login';
        return;
      }
      
      if (!response.ok) throw new Error('Like failed');
      
      // Toggle like state
      const isLiked = elements.likeButton.classList.contains('liked');
      
      if (isLiked) {
        // Unlike the song
        state.likedSongs = state.likedSongs.filter(song => song.id !== songId);
        elements.likeButton.classList.remove('liked');
        elements.likeButton.innerHTML = '<i class="far fa-thumbs-up"></i>';
      } else {
        // Like the song
        const song = state.currentPlaylist[state.currentSongIndex];
        if (song) {
          state.likedSongs = [song, ...state.likedSongs];
          elements.likeButton.classList.add('liked');
          elements.likeButton.innerHTML = '<i class="fas fa-thumbs-up"></i>';
        }
      }
      
      // Update favorites tab
      renderSongsToContainer(state.likedSongs, document.getElementById('favorites-songs'));
      
      // Animation
      elements.likeButton.style.transform = 'scale(1.2)';
      setTimeout(() => elements.likeButton.style.transform = 'scale(1)', 300);
    } catch (error) {
      console.error('Like error:', error);
    }
  }

  async function checkLikeStatus() {
    const songId = state.currentPlaylist[state.currentSongIndex]?.id;
    if (!songId) return;
  
    try {
      const response = await fetch(`/api/user/likes/${songId}`, {
        method: 'GET',
        credentials: 'include'
      });
  
      if (response.status === 401) {
        elements.likeButton.classList.remove('liked');
        elements.likeButton.innerHTML = '<i class="far fa-thumbs-up"></i>';
        return;
      }
  
      const data = await response.json();
      if (data.liked) {
        elements.likeButton.classList.add('liked');
        elements.likeButton.innerHTML = '<i class="fas fa-thumbs-up"></i>';
      } else {
        elements.likeButton.classList.remove('liked');
        elements.likeButton.innerHTML = '<i class="far fa-thumbs-up"></i>';
      }
    } catch (error) {
      console.error('Gagal cek status like:', error);
    }
  }  

  function updateLikeButton(songId) {
    const isLiked = state.likedSongs.some(song => song.id === songId);
    elements.likeButton.classList.toggle('liked', isLiked);
    elements.likeButton.innerHTML = isLiked ? '<i class="fas fa-thumbs-up"></i>' : '<i class="far fa-thumbs-up"></i>';
  }

  function expandPlayer() {
    state.isPlayerExpanded = true;
    elements.playerOverlay.classList.add('active');
    elements.playerExpanded.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function minimizePlayer() {
    state.isPlayerExpanded = false;
    elements.playerOverlay.classList.remove('active');
    elements.playerExpanded.classList.remove('active');
    document.body.style.overflow = '';
  }

  // ======================== SEARCH FUNCTIONS ========================
  function setupSearch() {
    const searchForm = document.querySelector('.search-form');
    
    if (searchForm) {
      searchForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const query = this.querySelector('.search-input').value.toLowerCase();
        performSearch(query);
      });
    }
  }

  function performSearch(query) {
    if (!query.trim()) {
      loadPublicTracks();
      return;
    }
    
    document.querySelectorAll('.playlist-card').forEach(card => {
      const title = card.querySelector('.playlist-name').textContent.toLowerCase();
      const artist = card.querySelector('.playlist-description').textContent.toLowerCase();
      card.style.display = (title.includes(query) || artist.includes(query)) ? 'block' : 'none';
    });
  }

  // ======================== TAB FUNCTIONS ========================
  function initTabs() {
    elements.tabButtons.forEach(button => {
      button.addEventListener('click', function() {
        elements.tabButtons.forEach(btn => btn.classList.remove('active'));
        this.classList.add('active');
        switchTab(this.dataset.tab);
      });
    });
  }

  function setupSidebarNavigation() {
    elements.sidebarItems.forEach(item => {
      item.addEventListener('click', function() {
        elements.sidebarItems.forEach(i => i.classList.remove('active'));
        this.classList.add('active');
        
        const tab = this.dataset.tab;
        const tabButton = document.querySelector(`.tab-button[data-tab="${tab}"]`);
        if (tabButton) {
          tabButton.click();
        } else {
          switchTab(tab);
        }
      });
    });
  }

  // ======================== PLAYLIST FUNCTIONS ========================
  function setupPlaylistModal() {
    elements.addPlaylistButton.addEventListener('click', function() {
      if (!state.isLoggedIn) {
        window.location.href = '/login';
        return;
      }
      elements.playlistModal.classList.add('active');
    });
    
    elements.closeModalButton.addEventListener('click', closeModal);
    elements.cancelButton.addEventListener('click', closeModal);
    
    elements.playlistModal.addEventListener('click', function(e) {
      if (e.target === this) closeModal();
    });
    
    elements.playlistForm.addEventListener('submit', async function(e) {
      e.preventDefault();
      
      const name = document.getElementById('playlist-name').value;
      const description = document.getElementById('playlist-description').value;
      
      try {
        const response = await fetch('/api/playlists', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ name, description }),
          credentials: 'include'
        });
        
        if (!response.ok) throw new Error('Failed to create playlist');
        
        const newPlaylist = await response.json();
        state.userPlaylists.push(newPlaylist);
        renderPlaylists(state.userPlaylists);
        
        // Reset form and close modal
        this.reset();
        closeModal();
      } catch (error) {
        console.error('Playlist creation error:', error);
      }
    });
    
    function closeModal() {
      elements.playlistModal.classList.remove('active');
    }
  }

  async function loadUserPlaylists() {
    if (!state.isLoggedIn) {
      showPlaceholder(document.getElementById('user-playlists'), 'fa-sign-in-alt', 'Sign in to view your playlists');
      return;
    }

    try {
      showLoader(document.getElementById('user-playlists'));
      
      const response = await fetch('/api/playlists', {
        credentials: 'include'
      });
      
      if (!response.ok) throw new Error('Failed to load playlists');
      
      state.userPlaylists = await response.json();
      renderPlaylists(state.userPlaylists);
    } catch (error) {
      console.error('Playlist loading error:', error);
      showError(document.getElementById('user-playlists'), 'Failed to load playlists');
    }
  }

  function renderPlaylists(playlists) {
    const container = document.getElementById('user-playlists');
    
    if (!playlists || playlists.length === 0) {
      showPlaceholder(container, 'fa-plus-circle', 'No playlists yet. Create one!');
      return;
    }
    
    container.innerHTML = playlists.map(playlist => `
      <div class="sidebar-item" data-playlist-id="${playlist.id}">
        <i class="fas fa-list"></i>
        <span>${playlist.name}</span>
      </div>
    `).join('');
    
    // Add click events to playlists
    container.querySelectorAll('.sidebar-item').forEach(item => {
      item.addEventListener('click', function() {
        const playlistId = this.dataset.playlistId;
        loadPlaylistSongs(playlistId);
      });
    });
  }

  async function loadPlaylistSongs(playlistId) {
    try {
      const response = await fetch(`/api/playlists/${playlistId}/songs`, {
        credentials: 'include'
      });
      
      if (!response.ok) throw new Error('Failed to load playlist songs');
      
      const songs = await response.json();
      
      // Create a temporary tab for the playlist
      const tabId = `playlist-${playlistId}`;
      const playlist = state.userPlaylists.find(p => p.id == playlistId);
      
      // Create tab if it doesn't exist
      if (!document.getElementById(`${tabId}-tab`)) {
        const tabsContainer = document.querySelector('.tabs');
        const tabButton = document.createElement('button');
        tabButton.className = 'tab-button';
        tabButton.dataset.tab = tabId;
        tabButton.textContent = playlist.name;
        tabsContainer.appendChild(tabButton);
        
        const tabContent = document.createElement('div');
        tabContent.id = `${tabId}-tab`;
        tabContent.className = 'tab-content';
        tabContent.innerHTML = `
          <h2 class="section-title">
            <i class="fas fa-list"></i>
            <span>${playlist.name}</span>
          </h2>
          <div class="playlist-grid" id="${tabId}-songs">
            <div class="loader">
              <i class="fas fa-spinner loader-spinner"></i>
              <span>Loading playlist songs...</span>
            </div>
          </div>
        `;
        document.querySelector('.content').appendChild(tabContent);
        
        // Add click handler for the new tab
        tabButton.addEventListener('click', function() {
          document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
          document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
          this.classList.add('active');
          document.getElementById(`${this.dataset.tab}-tab`).classList.add('active');
        });
      }
      
      // Render songs
      renderSongsToContainer(songs, document.getElementById(`${tabId}-songs`));
      
      // Activate the tab
      document.querySelector(`.tab-button[data-tab="${tabId}"]`).click();
    } catch (error) {
      console.error('Playlist songs loading error:', error);
    }
  }

  // ======================== SONG FUNCTIONS ========================
  async function loadPublicTracks() {
    try {
      showLoader(document.getElementById('recommended-songs'));
      showLoader(document.getElementById('all-songs'));
      showLoader(document.getElementById('trending-songs'));
      
      const response = await fetch('/api/player/songs');
      if (!response.ok) throw new Error('Failed to load songs');
      
      const songs = await response.json();
      state.currentPlaylist = songs;
      
      // Show 12 random recommended songs for first-time visitors
      if (!localStorage.getItem('hasVisitedBefore') && songs.length > 0) {
        const recommendedSongs = getRandomSongs(songs, 12);
        renderSongsToContainer(recommendedSongs, document.getElementById('recommended-songs'));
        localStorage.setItem('hasVisitedBefore', 'true');
      } else {
        showPlaceholder(document.getElementById('recommended-songs'), 'fa-home', 'Welcome back! Browse our music collection');
      }
      
      // Render all songs in the "All Songs" tab (random order)
      const allSongsRandom = getRandomSongs(songs, songs.length);
      renderSongsToContainer(allSongsRandom, document.getElementById('all-songs'));
      
      // Render trending songs with random songs
      renderSongsToContainer(getRandomSongs(songs, 12), document.getElementById('trending-songs'));
    } catch (error) {
      console.error('Songs loading error:', error);
      showError(document.getElementById('recommended-songs'), 'Failed to load songs');
    }
  }

  async function loadRecentSongs() {
    if (!state.isLoggedIn) {
      showPlaceholder(document.getElementById('recent-songs'), 'fa-sign-in-alt', 'Sign in to view your recently played songs');
      return;
    }

    try {
      showLoader(document.getElementById('recent-songs'));
      
      const response = await fetch('/api/history/recent', {
        credentials: 'include'
      });
      
      if (!response.ok) throw new Error('Failed to load recent songs');
      
      state.recentSongs = await response.json();
      
      if (state.recentSongs.length > 0) {
        renderSongsToContainer(state.recentSongs, document.getElementById('recent-songs'));
      } else {
        showPlaceholder(document.getElementById('recent-songs'), 'fa-clock', 'No recently played songs yet');
      }
    } catch (error) {
      console.error('Recent songs loading error:', error);
      showError(document.getElementById('recent-songs'), 'Failed to load recent songs');
    }
  }

  async function loadLikedSongs() {
    if (!state.isLoggedIn) {
      showPlaceholder(document.getElementById('favorites-songs'), 'fa-sign-in-alt', 'Sign in to view your liked songs');
      return;
    }

    try {
      showLoader(document.getElementById('favorites-songs'));
      
      const response = await fetch('/api/user/likes', {
        credentials: 'include'
      });
      
      if (!response.ok) throw new Error('Failed to load liked songs');
      
      state.likedSongs = await response.json();
      
      if (state.likedSongs.length > 0) {
        renderSongsToContainer(state.likedSongs, document.getElementById('favorites-songs'));
      } else {
        showPlaceholder(document.getElementById('favorites-songs'), 'fa-thumbs-up', 'No liked songs yet');
      }
    } catch (error) {
      console.error('Liked songs loading error:', error);
      showError(document.getElementById('favorites-songs'), 'Failed to load liked songs');
    }
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

  function renderSongsToContainer(songs, container) {
    if (!songs || !songs.length) {
      showPlaceholder(container, 'fa-music', 'No songs found');
      return;
    }
    
    container.innerHTML = songs.map(song => `
      <div class="playlist-card" data-song-id="${song.id}">
        <div class="playlist-image">
          <img src="${song.cover_url || '/public/thumbs/default.jpg'}" 
               alt="${song.title}" 
               loading="lazy"
               onerror="this.src='/public/thumbs/default.jpg'">
          <button class="play-button">
            <i class="fas fa-play"></i>
          </button>
        </div>
        <div class="playlist-info">
          <h3 class="playlist-name">${song.title || 'Untitled'}</h3>
          <p class="playlist-description">${song.artist || 'Unknown Artist'}</p>
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
      playBtn.addEventListener('click', function(e) {
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

  async function addToHistory(songId) {
    try {
      await fetch('/api/history/add', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ song_id: songId }),
        credentials: 'include'
      });
      
      // Update recent songs in state
      const song = state.currentPlaylist.find(s => s.id == songId);
      if (song) {
        state.recentSongs = [song, ...state.recentSongs.filter(s => s.id != songId)];
        renderSongsToContainer(state.recentSongs, document.getElementById('recent-songs'));
      }
    } catch (error) {
      console.error('History update error:', error);
    }
  }

  // Service Worker Registration
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js')
      .then(() => console.log('Service Worker registered'))
      .catch(error => console.error('Service Worker registration failed:', error));
  }

  function switchTab(tabId) {
    // Hide all tab contents
    elements.tabContents.forEach(content => {
      content.classList.remove('active');
    });
    
    // Show selected tab content
    const tabContent = document.getElementById(`${tabId}-tab`);
    if (tabContent) {
      tabContent.classList.add('active');
      
      // Load data if needed
      if (tabId === 'all' && state.currentPlaylist.length === 0) {
        loadPublicTracks();
      } else if (tabId === 'favorites' && state.likedSongs.length === 0) {
        loadLikedSongs();
      } else if (tabId === 'recent' && state.recentSongs.length === 0) {
        loadRecentSongs();
      }
    }
  }