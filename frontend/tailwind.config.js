/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./src/**/*.{html,ts}",
    ],
    theme: {
        extend: {
            colors: {
                primary: '#00ff00',   // Terminal Green
                secondary: '#00cc00', // Darker Green
                background: '#000000', // True Black
                surface: '#111111',    // Slightly off-black
                muted: '#666666',      // Gray
            },
            fontFamily: {
                mono: ['"Courier Prime"', 'Courier', 'monospace'],
                sans: ['"Courier Prime"', 'Courier', 'monospace'],
            },
        },
    },
    plugins: [],
}
