document.getElementById("login-form").addEventListener("submit", async function(e) {
    e.preventDefault();
    
    const email_or_username = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;
    
    const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            email_or_username,
            password
        })
    });
    
    const result = await response.json();
    const msgBox = document.getElementById("response-message");
    
    if (response.ok) {
        msgBox.style.color = "lightgreen";
        msgBox.textContent = "Login berhasil! Mengalihkan...";
        setTimeout(() => {
            window.location.href = "/";
        }, 1500);
    } else {
        msgBox.style.color = "salmon";
        msgBox.textContent = result.error || "Login gagal.";
    }
});

// Google login redirect
document.querySelector('.google-btn').addEventListener('click', () => {
    window.location.href = "/api/auth/google";
});
