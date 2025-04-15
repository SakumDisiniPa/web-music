// search-lagu.min.js
document.getElementById('search-form').addEventListener('submit',function(e){e.preventDefault();const searchTerm=document.getElementById('search-input').value.toLowerCase();const tracks=document.querySelectorAll('.playlist-card');tracks.forEach(track=>{const title=track.querySelector('h3').textContent.toLowerCase();const artist=track.querySelector('p').textContent.toLowerCase();const description=track.querySelector('.description')?.textContent.toLowerCase()||'';track.style.display=(title.includes(searchTerm)||artist.includes(searchTerm)||description.includes(searchTerm))?'block':'none'})});document.addEventListener('click',function(e){if(e.target&&e.target.classList.contains('download-btn')){const youtubeUrl=e.target.getAttribute('data-url');fetch('/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:youtubeUrl})}).then(response=>response.json()).then(data=>{if(data.message){alert(data.message);const audio=new Audio(`/audio/${data.file}`);audio.play()}else{alert('Gagal mendownload lagu.')}}).catch(error=>{console.error('Error:',error);alert('Terjadi kesalahan saat mendownload.')})}});fetch('/api/search-lagu').then(response=>response.json()).then(data=>{const searchResults=document.getElementById('search-results');data.forEach(lagu=>{const card=document.createElement('div');card.classList.add('playlist-card');card.innerHTML=`<img src="${lagu.thumbnail}" alt="${lagu.title}"><div class="info"><h3>${lagu.title}</h3><p>${lagu.channel}</p><button class="download-btn" data-url="${lagu.url}">Download & Putar</button></div>`;searchResults.appendChild(card)})}).catch(error=>console.error('Error fetching search results:',error));
