    // Fungsi untuk tab functionality
    document.querySelectorAll('.tab, .nav-link[data-tab]').forEach(tab => {
        tab.addEventListener('click', function() {
            const tabId = this.dataset.tab;
            
            // Update active tab
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document
            .querySelectorAll('.nav-link').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            // Find corresponding nav link
            if (this.classList.contains('tab')) {
                document.querySelector(`.nav-link[data-tab="${tabId}"]`).classList.add('active');
            } else {
                document.querySelector(`.tab[data-tab="${tabId}"]`).classList.add('active');
            }
            
            // Update active content
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(`${tabId}-tab`).classList.add('active');
            
            // Update page title
            document.getElementById('page-title').textContent = 
                this.textContent.trim() + (tabId === 'dashboard' ? ' Admin' : '');
            
            // Load data if needed
            if (tabId === 'songs') {
                loadSongs();
            } else if (tabId === 'users') {
                loadUsers();
            }
        });
    });

    // Fungsi untuk memuat data lagu
    async function loadSongs() {
        try {
            const response = await fetch('/api/player/songs');
            const songs = await response.json();
            
            // Update stats
            document.getElementById('total-songs').textContent = songs.length;
            document.getElementById('total-plays').textContent = songs.reduce((sum, song) => sum + (song.plays || 0), 0);
            document.getElementById('total-likes').textContent = songs.reduce((sum, song) => sum + (song.likes || 0), 0);
            
            // Populate table
            const tableBody = document.getElementById('songs-list');
            tableBody.innerHTML = '';
            
            songs.forEach((song, index) => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${index + 1}</td>
                    <td>${song.title}</td>
                    <td>${song.artist}</td>
                    <td>${song.genre || '-'}</td>
                    <td>${song.plays || 0}</td>
                    <td>${song.likes || 0}</td>
                    <td>
                        <a href="/public/edit.html?id=${song.id}" class="btn btn-edit">
                            <i class="fas fa-edit"></i> Edit
                        </a>
                        <button class="btn btn-delete" onclick="deleteSong(${song.id})">
                            <i class="fas fa-trash"></i> Hapus
                        </button>
                    </td>
                `;
                tableBody.appendChild(row);
            });
        } catch (error) {
            console.error('Error loading songs:', error);
            alert('Gagal memuat data lagu: ' + error.message);
        }
    }

    // Fungsi untuk memuat data pengguna
    async function loadUsers() {
        try {
            const response = await fetch('/api/users');
            
            // Periksa status response
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const users = await response.json();
            
            // Debug: log data ke console
            console.log('Data users dari API:', users);
            
            // Pastikan data adalah array
            if (!Array.isArray(users)) {
                throw new Error('Data users bukan array');
            }
            
            // Update statistik total pengguna
            document.getElementById('total-users').textContent = users.length;
            
            // Populate table
            const tableBody = document.getElementById('users-list');
            tableBody.innerHTML = '';
            
            // Cek apakah data memiliki field yang diperlukan
            const sampleUser = users[0] || {};
            const hasIsActive = 'is_active' in sampleUser;
            const hasCreatedAt = 'created_at' in sampleUser;
            
            users.forEach((user) => {
                const row = document.createElement('tr');
                
                // Handle missing fields with fallback values
                const avatarUrl = user.avatar || 
                    'https://ui-avatars.com/api/?name=' + 
                    encodeURIComponent(user.username || 'U') + 
                    '&background=random';
                    
                const isActive = hasIsActive ? user.is_active : true;
                const createdAt = hasCreatedAt && user.created_at ? 
                    new Date(user.created_at).toLocaleDateString() : 
                    'N/A';
                
                row.innerHTML = `
                    <td>
                        <img src="${avatarUrl}" 
                            class="user-avatar" 
                            alt="${user.username || 'User'}" loading="lazy">
                    </td>
                    <td>${user.username || 'N/A'}</td>
                    <td>${user.email || 'N/A'}</td>
                    <td>
                        <span class="badge ${isActive ? 'badge-active' : 'badge-inactive'}">
                            ${isActive ? 'Aktif' : 'Nonaktif'}
                        </span>
                    </td>
                    <td>${createdAt}</td>
                    <td>
                        <button class="btn btn-edit" onclick="editUser(${user.id || 'null'})">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                        <button class="btn btn-delete" onclick="deleteUser(${user.id || 'null'})">
                            <i class="fas fa-trash"></i> Hapus
                        </button>
                    </td>
                `;
                tableBody.appendChild(row);
            });
            
        } catch (error) {
            console.error('Error loading users:', error);
            
            // Tampilkan pesan error yang lebih informatif
            const errorMessage = error.message.includes('Unknown column') ? 
                'Struktur database tidak sesuai. Silakan periksa backend.' :
                'Gagal memuat data pengguna: ' + error.message;
                
            // Tampilkan di console dan UI
            alert(errorMessage);
            
            // Tampilkan pesan error di tabel
            const tableBody = document.getElementById('users-list');
            if (tableBody) {
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="6" style="color: red; text-align: center; padding: 20px;">
                            ${errorMessage}
                            <br><small>Lihat console untuk detail error</small>
                        </td>
                    </tr>
                `;
            }
        }
    }

    // Fungsi untuk menghapus lagu
    async function deleteSong(songId) {
        if (confirm('Apakah Anda yakin ingin menghapus lagu ini?')) {
            try {
                const response = await fetch(`/api/player/songs/${songId}`, {
                    method: 'DELETE'
                });
                
                if (response.ok) {
                    alert('Lagu berhasil dihapus');
                    loadSongs(); // Refresh list
                } else {
                    alert('Gagal menghapus lagu');
                }
            } catch (error) {
                console.error('Error deleting song:', error);
                alert('Terjadi kesalahan saat menghapus lagu');
            }
        }
    }

    // Fungsi untuk edit pengguna
    function editUser(userId) {
        console.log('Edit user dengan ID:', userId);
        alert('Fitur edit pengguna dengan ID: ' + userId + ' belum diimplementasikan');
    }

    // Fungsi untuk hapus pengguna
    async function deleteUser(userId) {
        if (confirm('Apakah Anda yakin ingin menghapus pengguna ini?')) {
            try {
                const response = await fetch(`/api/users/${userId}`, {
                    method: 'DELETE'
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    alert(result.message || 'Pengguna berhasil dihapus');
                    loadUsers(); // Refresh daftar pengguna
                } else {
                    throw new Error(result.error || 'Gagal menghapus pengguna');
                }
            } catch (error) {
                console.error('Error deleting user:', error);
                alert('Terjadi kesalahan saat menghapus pengguna: ' + error.message);
            }
        }
    }

    // Memuat data saat halaman dimuat
    document.addEventListener('DOMContentLoaded', () => {
        loadSongs();
        loadUsers(); // Memuat data pengguna saat pertama kali halaman dimuat
    });