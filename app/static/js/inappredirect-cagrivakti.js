(function () {

    const ua = navigator.userAgent || navigator.vendor || window.opera;

    const isAndroid = /Android/i.test(ua);
    const isInApp = /FBAN|FBAV|Instagram|TikTok|Telegram|Snapchat|Line|Musical-ly|WhatsApp|FB_IAB|FB4A|Twitter|Pinterest|MicroMessenger/i.test(ua);

    if (!isAndroid || !isInApp) return;

    if (sessionStorage.getItem('chrome_intent_attempted')) return;
    sessionStorage.setItem('chrome_intent_attempted', '1');

    const url = window.location.href.replace(/^https?:\/\//, '');
    const intentUrl = `intent://${url}#Intent;scheme=https;package=com.android.chrome;end`;

    let redirected = false;

    document.addEventListener("visibilitychange", function () {
        if (document.hidden) {
            redirected = true;
        }
    });

    window.location.href = intentUrl;

    setTimeout(function () {
        if (!redirected) {
            showOpenInBrowserModal();
        }
    }, 900);

    function showOpenInBrowserModal() {

        const modal = document.createElement("div");
        modal.id = "open-browser-modal";
        modal.innerHTML = `
            <div class="ob-overlay">
                <div class="ob-box">
                    <button id="ob-close-btn" class="ob-close">&times;</button>
                    <h3>Tarayıcıda Açın</h3>
                    <p>Instagram içi tarayıcı bazı özellikleri kısıtlıyor. 
                    Daha hızlı ve sorunsuz deneyim için Chrome'da açın.</p>
                    <button id="copyLinkBtn">Bağlantıyı Kopyala</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Çarpı butonu
        document.getElementById("ob-close-btn").addEventListener("click", function () {
            modal.remove();
        });

        // Bağlantı kopyalama
        document.getElementById("copyLinkBtn").addEventListener("click", function () {
            navigator.clipboard.writeText(window.location.href);
            this.innerText = "Kopyalandı ✓";
        });

        injectModalStyle();
    }

    function injectModalStyle() {
        if (document.getElementById("ob-style")) return;

        const style = document.createElement("style");
        style.id = "ob-style";
        style.innerHTML = `
            .ob-overlay {
                position: fixed;
                inset: 0;
                background: rgba(0,0,0,0.75);
                backdrop-filter: blur(6px);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 99999;
                animation: fadeIn 0.25s ease;
            }

            .ob-box {
                background: #1c1c1c;
                padding: 24px;
                border-radius: 16px;
                width: 85%;
                max-width: 380px;
                text-align: center;
                box-shadow: 0 15px 40px rgba(0,0,0,0.4);
                position: relative;
            }

            .ob-box h3 {
                margin: 0 0 10px;
                font-size: 18px;
                color: #FFC107;
            }

            .ob-box p {
                font-size: 14px;
                color: #ccc;
                margin-bottom: 18px;
                line-height: 1.5;
            }

            .ob-box button {
                background: #FFC107;
                border: none;
                padding: 10px 18px;
                border-radius: 8px;
                font-weight: 600;
                cursor: pointer;
            }

            #copyLinkBtn {
                margin-top: 10px;
            }

            .ob-close {
                position: absolute;
                top: 8px;
                right: 10px;
                background-color: transparent;
                border: none;
                font-size: 20px;
                color: #121212;
                cursor: pointer;
                line-height: 1;
            }

            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }

})();