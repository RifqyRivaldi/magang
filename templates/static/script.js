$(document).ready(function() {
    // Fungsi untuk memperbarui dashboard dengan data dari server
    function updateDashboard() {
        $.ajax({
            url: "/data", // Endpoint Flask yang mengirim data deteksi
            method: "GET",
            success: function(data) {
                // Update nilai di dashboard
                $('#peopleCount').text(data.people);
                $('#carCount').text(data.cars);
                $('#motorCount').text(data.motorcycles);

                // Update waktu terbaru
                var now = new Date();
                var formattedTime = now.getHours().toString().padStart(2, '0') + ':' +
                                    now.getMinutes().toString().padStart(2, '0') + ':' +
                                    now.getSeconds().toString().padStart(2, '0');
                $('#timestamp').text(formattedTime);
            },
            error: function(err) {
                console.error("Gagal mendapatkan data", err);
            }
        });
    }

    // Jalankan updateDashboard setiap 2 detik
    setInterval(updateDashboard, 2000);
});