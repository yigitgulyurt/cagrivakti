(function() {
    const hash = location.hash.replace('#', '');
    const supported = ['tr', 'en'];
    const locale = supported.includes(hash) ? hash : null;

    if (locale && localStorage.getItem('locale') !== locale) {
        localStorage.setItem('locale', locale);
        location.reload();
    }
})();