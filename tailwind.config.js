/** Tailwind v3 — konfigurasi build statis (pengganti Play CDN).
 *  Palet "orvelion" dipindahkan dari inline config yang dulu ada di base.html.
 *  Regenerasi CSS setelah menambah/mengubah kelas: jalankan tools/build-css.sh
 */
module.exports = {
  content: ["./templates/**/*.html", "./static/js/**/*.js"],
  theme: {
    extend: {
      colors: {
        orvelion: {
          coral: "#FD8C5A",
          rust: "#9C381C",
          peach: "#FDB18F",
          ember: "#D9530D",
          apricot: "#FFAE7A",
          amber: "#FFD495",
          lilac: "#F9EDFF",
          blush: "#FFE7ED",
          rose: "#E6B1B5",
          dark: "#0d0b0a",
          surface: "#151210",
          card: "#1c1714",
        },
      },
    },
  },
};
