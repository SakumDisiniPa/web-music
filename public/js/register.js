document.getElementById("register-form").addEventListener("submit", async function(e) {
    e.preventDefault();
    
    const username = document.getElementById("username").value.trim();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    
    const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            username,
            email,
            password
        })
    });
    
    const result = await response.json();
    const msgBox = document.getElementById("response-message");
    
    if (response.ok) {
        msgBox.style.color = "lightgreen";
        msgBox.textContent = "Akun berhasil dibuat! Silakan cek email untuk verifikasi.";
        document.getElementById("register-form").reset();
    } else {
        msgBox.style.color = "salmon";
        msgBox.textContent = result.error || "Terjadi kesalahan saat mendaftar.";
    }
});

// Google register redirect
document.querySelector('.google-btn').addEventListener('click', () => {
    window.location.href = "/api/auth/google";
});
