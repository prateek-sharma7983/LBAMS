setTimeout(() => {
    document.querySelectorAll(".flash").forEach((element) => {
        element.style.opacity = "0";
        setTimeout(() => element.remove(), 300);
    });
}, 3000);
