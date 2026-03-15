/**
 * Hub — entrance animations for game cards
 * Staggered reveal, no bounce
 */

document.addEventListener('DOMContentLoaded', () => {
    const cards = document.querySelectorAll('.hub-card');
    const delays = { 0: 120, 1: 220, 2: 320 };

    const reveal = () => {
        cards.forEach((card) => {
            const delayKey = card.dataset.delay ?? 0;
            const ms = delays[delayKey] ?? 200;
            setTimeout(() => card.classList.add('is-visible'), ms);
        });
    };

    if (document.visibilityState === 'visible') {
        reveal();
    } else {
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') reveal();
        });
    }
});
