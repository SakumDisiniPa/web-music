        // Global variables
        let originalData = {};
        let currentSongId = null;
        
        // Initialize when page loads
        document.addEventListener('DOMContentLoaded', function() {
            // Get song ID from URL
            const urlParams = new URLSearchParams(window.location.search);
            currentSongId = urlParams.get('id');
            
            if (!currentSongId) {
                showError('ID lagu tidak valid');
                return;
            }
            
            document.getElementById('songId').value = currentSongId;
            loadSongData(currentSongId);
        });
        
        // Load song data from API
        function loadSongData(songId) {
            showLoading(true);
            
            fetch(`/api/player/songs/${songId}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Gagal memuat data lagu');
                    }
                    return response.json();
                })
                .then(data => {
                    // Store original data
                    originalData = {
                        judul: data.judul || data.title,
                        artis: data.artis || data.artist,
                        genre: data.genre || 'other',
                        deskripsi: data.deskripsi || data.description,
                        thumbnail: data.thumbnail || data.cover_url.replace('/public/thumbs/', '')
                    };
                    
                    // Populate form fields
                    document.getElementById('judulLagu').value = originalData.judul;
                    document.getElementById('namaArtis').value = originalData.artis;
                    document.getElementById('genreLagu').value = originalData.genre;
                    document.getElementById('deskripsiLagu').value = originalData.deskripsi;
                    document.getElementById('originalThumbnail').value = originalData.thumbnail;
                    
                    // Display current thumbnail
                    if (originalData.thumbnail) {
                        const thumbnailImg = document.getElementById('currentThumbnail');
                        thumbnailImg.src = `/public/thumbs/${originalData.thumbnail}`;
                        thumbnailImg.style.display = 'block';
                        document.getElementById('thumbnailPlaceholder').style.display = 'none';
                    }
                    
                    showLoading(false);
                })
                .catch(error => {
                    showError(error.message);
                    showLoading(false);
                });
        }
        
        // Handle thumbnail upload
        function handleThumbnailUpload(input) {
            if (input.files && input.files[0]) {
                const reader = new FileReader();
                const preview = document.getElementById('thumbnailPreview');
                const placeholder = document.getElementById('thumbnailPlaceholder');
                const currentThumbnail = document.getElementById('currentThumbnail');
                const resetBtn = document.getElementById('resetThumbnailBtn');
                
                reader.onload = function(e) {
                    currentThumbnail.src = e.target.result;
                    currentThumbnail.style.display = 'block';
                    placeholder.style.display = 'none';
                    resetBtn.style.display = 'inline-block';
                    checkChanges();
                }
                
                reader.readAsDataURL(input.files[0]);
            }
        }
        
        // Reset thumbnail to original
        function resetThumbnail() {
            const fileInput = document.getElementById('fileInput');
            const resetBtn = document.getElementById('resetThumbnailBtn');
            const currentThumbnail = document.getElementById('currentThumbnail');
            const placeholder = document.getElementById('thumbnailPlaceholder');
            
            fileInput.value = '';
            resetBtn.style.display = 'none';
            
            if (originalData.thumbnail) {
                currentThumbnail.src = `/public/thumbs/${originalData.thumbnail}`;
                currentThumbnail.style.display = 'block';
                placeholder.style.display = 'none';
            } else {
                currentThumbnail.style.display = 'none';
                placeholder.style.display = 'block';
            }
            
            checkChanges();
        }
        
        // Check for changes in form
        function checkChanges() {
            const saveBtn = document.getElementById('tombolSimpan');
            const fileInput = document.getElementById('fileInput');
            
            const currentData = {
                judul: document.getElementById('judulLagu').value,
                artis: document.getElementById('namaArtis').value,
                genre: document.getElementById('genreLagu').value,
                deskripsi: document.getElementById('deskripsiLagu').value,
                thumbnailChanged: fileInput.files.length > 0
            };
            
            // Check if any field has changed
            const hasChanged = (
                currentData.judul !== originalData.judul ||
                currentData.artis !== originalData.artis ||
                currentData.genre !== originalData.genre ||
                currentData.deskripsi !== originalData.deskripsi ||
                currentData.thumbnailChanged
            );
            
            // Update indicators
            document.getElementById('indikatorJudul').style.display = 
                currentData.judul !== originalData.judul ? 'inline' : 'none';
            document.getElementById('indikatorArtis').style.display = 
                currentData.artis !== originalData.artis ? 'inline' : 'none';
            document.getElementById('indikatorGenre').style.display = 
                currentData.genre !== originalData.genre ? 'inline' : 'none';
            document.getElementById('indikatorDeskripsi').style.display = 
                currentData.deskripsi !== originalData.deskripsi ? 'inline' : 'none';
            
            saveBtn.disabled = !hasChanged;
        }
        
        // Handle form submission
        document.getElementById('formEdit').addEventListener('submit', function(e) {
            e.preventDefault();
            showLoading(true);
            
            const formData = new FormData(this);
            
            fetch('/api/player/songs/update', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.message || 'Gagal memperbarui lagu'); });
                }
                return response.json();
            })
            .then(data => {
                showSuccess('Perubahan berhasil disimpan!');
                // Update original data with new values
                originalData = {
                    judul: document.getElementById('judulLagu').value,
                    artis: document.getElementById('namaArtis').value,
                    genre: document.getElementById('genreLagu').value,
                    deskripsi: document.getElementById('deskripsiLagu').value,
                    thumbnail: data.newThumbnail || originalData.thumbnail
                };
                
                // Reset thumbnail if it was changed
                if (document.getElementById('fileInput').files.length > 0) {
                    document.getElementById('fileInput').value = '';
                    document.getElementById('resetThumbnailBtn').style.display = 'none';
                    
                    if (originalData.thumbnail) {
                        document.getElementById('currentThumbnail').src = `/public/thumbs/${originalData.thumbnail}`;
                    }
                }
                
                checkChanges(); // This will disable the save button again
                showLoading(false);
            })
            .catch(error => {
                showError(error.message);
                showLoading(false);
            });
        });
        
        // Confirm delete action
        function confirmDelete() {
            if (confirm('Apakah Anda yakin ingin menghapus lagu ini? Aksi ini tidak dapat dibatalkan.')) {
                showLoading(true);
                
                fetch(`/api/player/songs/${currentSongId}`, {
                    method: 'DELETE'
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Gagal menghapus lagu');
                    }
                    return response.json();
                })
                .then(data => {
                    alert('Lagu berhasil dihapus');
                    window.location.href = '/admin';
                })
                .catch(error => {
                    showError(error.message);
                    showLoading(false);
                });
            }
        }
        
        // Helper functions
        function showLoading(show) {
            document.getElementById('loadingOverlay').style.display = show ? 'flex' : 'none';
        }
        
        function showError(message) {
            const errorElement = document.getElementById('errorMessage');
            errorElement.textContent = message;
            errorElement.style.display = 'block';
            
            // Hide after 5 seconds
            setTimeout(() => {
                errorElement.style.display = 'none';
            }, 5000);
        }
        
        function showSuccess(message) {
            const successElement = document.getElementById('successMessage');
            successElement.textContent = message;
            successElement.style.display = 'block';
            
            // Hide after 3 seconds
            setTimeout(() => {
                successElement.style.display = 'none';
            }, 3000);
        }