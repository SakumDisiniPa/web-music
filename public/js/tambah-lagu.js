// Tab functionality
const tabs = document.querySelectorAll('.tab-button');
tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab-button').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        const tabId = tab.getAttribute('data-tab');
        document.getElementById(`${tabId}-tab`).classList.add('active');
    });
});

// DOM elements
const youtubeForm = document.getElementById('youtubeForm');
const spotifyForm = document.getElementById('spotifyForm');
const playlistForm = document.getElementById('playlistForm');
const resultDiv = document.getElementById('result');
const youtubeDownloadBtn = document.getElementById('youtubeDownloadBtn');
const spotifyDownloadBtn = document.getElementById('spotifyDownloadBtn');
const playlistDownloadBtn = document.getElementById('playlistDownloadBtn');
const progressBar = document.getElementById('progressBar');
const progressText = document.getElementById('progressText');
const playlistResults = document.getElementById('playlistResults');

// Utility functions
function showResult(message, type) {
    resultDiv.innerHTML = `<div class="${type}">${message}</div>`;
}

function showTrackInfo(track) {
    // Handle case when track data is missing or incomplete
    if (!track) {
        return `<div class="track-info">
            <p><strong>Judul:</strong> Tidak diketahui</p>
            <p><strong>Artis:</strong> Tidak diketahui</p>
            <img src="/default-thumbnail.jpg" alt="Album cover">
        </div>`;
    }

    return `<div class="track-info">
        <p><strong>Judul:</strong> ${track.judul || "Tidak diketahui"}</p>
        <p><strong>Artis:</strong> ${track.artis || "Tidak diketahui"}</p>
        ${track.deskripsi ? `<p><strong>Deskripsi:</strong> ${track.deskripsi}</p>` : ""}
        <img src="${track.thumbnail || "/default-thumbnail.jpg"}" alt="Album cover">
    </div>`;
}

function updatePlaylistProgress(current, total, successCount, errorCount) {
    const percentage = Math.round((current / total) * 100);
    progressBar.style.width = `${percentage}%`;
    progressText.textContent = `Memproses ${current} dari ${total} lagu (${successCount} berhasil, ${errorCount} gagal)`;
}

function showPlaylistResults(successfulTracks, failedTracks) {
    playlistResults.innerHTML = '';
    
    if (successfulTracks.length > 0) {
        const successSection = document.createElement('div');
        successSection.innerHTML = `<h3>${successfulTracks.length} Lagu Berhasil Diunduh</h3>`;
        successfulTracks.forEach(track => {
            successSection.innerHTML += showTrackInfo(track);
        });
        playlistResults.appendChild(successSection);
    }
    
    if (failedTracks.length > 0) {
        const errorSection = document.createElement('div');
        errorSection.innerHTML = `<h3>${failedTracks.length} Lagu Gagal Diunduh</h3>`;
        failedTracks.forEach(error => {
            errorSection.innerHTML += `<div class="error">${error}</div>`;
        });
        playlistResults.appendChild(errorSection);
    }
}

// YouTube Form Handler
youtubeForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const youtubeUrl = document.getElementById('youtubeUrl').value;
    
    if (!youtubeUrl.includes('youtube.com') && !youtubeUrl.includes('youtu.be')) {
        showResult('❌ Masukkan URL YouTube yang valid', 'error');
        return;
    }

    youtubeDownloadBtn.disabled = true;
    showResult('⏳ Memproses lagu dari YouTube...', 'loading');

    try {
        // Step 1: Get metadata
        const metadataRes = await fetch('/admin/get-metadata', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: youtubeUrl })
        });

        if (!metadataRes.ok) {
            throw new Error('Gagal mengambil metadata');
        }

        const metadata = await metadataRes.json();
        
        if (!metadata.success) {
            throw new Error(metadata.error || 'Metadata tidak valid');
        }

        // Gunakan nilai default jika metadata tidak lengkap
        const judul = metadata.judul || 'Tidak diketahui';
        const artis = metadata.artis || 'Tidak diketahui';
        const deskripsi = metadata.deskripsi || '';
        const thumbnail = metadata.thumbnail || '/default-thumbnail.jpg';

        // Step 2: Upload with fallback metadata
        const uploadRes = await fetch('/admin/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: youtubeUrl,
                judul: judul,
                artis: artis,
                deskripsi: deskripsi,
                thumbnail: thumbnail
            })
        });

        const data = await uploadRes.json();
        
        if (uploadRes.ok && data.success) {
            // Siapkan informasi lagu lengkap untuk ditampilkan
            const trackInfo = {
                judul: data.judul || judul,
                artis: data.artis || artis,
                deskripsi: data.deskripsi || deskripsi,
                thumbnail: data.thumbnail || thumbnail
            };
            
            resultDiv.innerHTML = `
                <div class="success">✅ <strong>${data.message}</strong></div>
                ${showTrackInfo(trackInfo)}
            `;
            youtubeForm.reset();
        } else {
            throw new Error(data.error || 'Upload gagal');
        }
    } catch (err) {
        console.error(err);
        showResult(`❌ ${err.message || 'Terjadi kesalahan saat memproses YouTube'}`, 'error');
    } finally {
        youtubeDownloadBtn.disabled = false;
    }
});


// Spotify Form Handler
spotifyForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const spotifyUrl = document.getElementById('spotifyUrl').value;
    
    if (!spotifyUrl.includes('spotify.com')) {
        showResult('❌ Masukkan URL Spotify yang valid', 'error');
        return;
    }

    spotifyDownloadBtn.disabled = true;
    showResult('⏳ Memproses lagu dari Spotify...', 'loading');

    try {
        const res = await fetch('/admin/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                url: spotifyUrl,
                judul: null,
                artis: null,
                deskripsi: null
            })
        });

        const data = await res.json();
        
        if (res.ok && data.success) {
            // Ensure we have complete track info
            const trackInfo = {
                judul: data.judul || "Tidak diketahui",
                artis: data.artis || "Tidak diketahui",
                deskripsi: data.deskripsi || '',
                thumbnail: data.thumbnail || '/default-thumbnail.jpg'
            };
            
            resultDiv.innerHTML = `
                <div class="success">✅ <strong>${data.message}</strong></div>
                ${showTrackInfo(trackInfo)}
            `;
            spotifyForm.reset();
        } else {
            throw new Error(data.error || 'Upload gagal');
        }
    } catch (err) {
        console.error(err);
        showResult(`❌ ${err.message || 'Terjadi kesalahan saat memproses Spotify'}`, 'error');
    } finally {
        spotifyDownloadBtn.disabled = false;
    }
});

// Playlist Form Handler
playlistForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = document.getElementById('playlistUrl').value;
    
    progressBar.style.width = '0%';
    progressText.textContent = 'Memulai...';
    playlistResults.innerHTML = '';
    document.getElementById('playlistProgress').style.display = 'block';
    
    const eventSource = new EventSource(`/admin/download-playlist?url=${encodeURIComponent(url)}`);
    
    eventSource.onmessage = (e) => {
        const data = JSON.parse(e.data);
        
        if (data.error) {
            showResult(`❌ ${data.error}`, 'error');
            eventSource.close();
            return;
        }
        
        if (data.total) {
            progressText.textContent = `Memproses 0 dari ${data.total} lagu...`;
        }
        
        if (data.current) {
            const percent = Math.round((data.current / data.total) * 100);
            progressBar.style.width = `${percent}%`;
            
            let statusMsg = `Memproses ${data.current}/${data.total}`;
            if (data.message) statusMsg += ` - ${data.message}`;
            if (data.success) statusMsg += ` (${data.success} berhasil)`;
            if (data.failed) statusMsg += ` (${data.failed} gagal)`;
            
            progressText.textContent = statusMsg;
        }
        
        if (data.status === 'completed') {
            eventSource.close();
            showResult(`✅ Selesai! ${data.success}/${data.total} lagu berhasil`, 'success');
            
            if (data.failed > 0) {
                const errorDiv = document.createElement('div');
                errorDiv.innerHTML = `<h4>Gagal memproses ${data.failed} lagu:</h4>`;
                data.errors.forEach(err => {
                    errorDiv.innerHTML += `<div class="error">${err}</div>`;
                });
                playlistResults.appendChild(errorDiv);
            }
        }
    };
    
    eventSource.onerror = () => {
        showResult('❌ Koneksi terputus', 'error');
        eventSource.close();
    };
});