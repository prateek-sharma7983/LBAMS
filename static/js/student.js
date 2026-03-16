async function postAttendance(subjectId, latitude, longitude) {
    const formData = new FormData();
    formData.append("subject_id", subjectId);
    if (latitude !== undefined && longitude !== undefined) {
        formData.append("latitude", latitude);
        formData.append("longitude", longitude);
    }

    const response = await fetch("/student/mark-attendance", {
        method: "POST",
        body: formData,
    });
    return response.json();
}

function setMessage(message, isError = false) {
    const container = document.getElementById("attendance-message");
    container.textContent = message;
    container.style.color = isError ? "#b91c1c" : "#166534";
}

document.querySelectorAll(".attendance-trigger").forEach((button) => {
    button.addEventListener("click", async () => {
        const subjectId = button.dataset.subjectId;
        const subjectName = button.dataset.subjectName;
        if (!navigator.geolocation) {
            setMessage("Geolocation is not supported by this browser.", true);
            return;
        }
        setMessage(`Fetching location for ${subjectName}...`);
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                const { latitude, longitude } = position.coords;
                const result = await postAttendance(subjectId, latitude, longitude);
                setMessage(result.message, !result.ok);
                if (result.ok) {
                    setTimeout(() => window.location.reload(), 1200);
                }
            },
            () => {
                setMessage("Location access is required to mark attendance.", true);
            },
            { enableHighAccuracy: false, timeout: 10000 }
        );
    });
});
