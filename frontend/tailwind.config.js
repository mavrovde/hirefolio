/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./src/**/*.{html,ts}",
    ],
    theme: {
        extend: {
            colors: {
                primary: '#00ff00',
                secondary: '#00cc00',
                background: '#000000',
                surface: '#111111',
                muted: '#666666',
            },
            fontFamily: {
                mono: ['"Courier Prime"', 'Courier', 'monospace'],
                sans: ['"Courier Prime"', 'Courier', 'monospace'], // Override sans to force mono everywhere
            },
        },
    },
    plugins: [],
}
