// Periksa status data setiap 3 detik
setInterval(() => {
    fetch('/data')
        .then(response => response.json())
        .then(data => {
            // Alert jika lebih dari 2 orang
            if (data.is_alert_orang) {
                alert(`Keramaian terdeteksi: ${data.orang} orang!`);
            }
            // Alert jika lebih dari 2 mobil
            if (data.is_alert_mobil) {
                alert(`Keramaian terdeteksi: ${data.mobil} mobil!`);
            }
            // Alert jika lebih dari 2 motor
            if (data.is_alert_motor) {
                alert(`Keramaian terdeteksi: ${data.motor} motor!`);
            }
        })
        .catch(error => console.error("Error fetching data:", error));
}, 3000); // Interval 3000ms (3 detik)
