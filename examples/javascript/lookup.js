// Contoh: cari satu entri Strong's berdasarkan nomornya.
// Jalankan: node lookup.js H430
//
// Jika dipasang lewat npm:
//   npm install strongs-dictionary-json
//   const dictionary = require("strongs-dictionary-json");

const fs = require("fs");
const path = require("path");

const dictionaryPath = path.join(__dirname, "../../data/combined/strongs-full.json");
const dictionary = JSON.parse(fs.readFileSync(dictionaryPath, "utf-8"));

function lookup(strongNumber) {
  return dictionary.find((entry) => entry.strong_number === strongNumber);
}

const query = process.argv[2] || "H430";
const result = lookup(query);

if (!result) {
  console.log(`Nomor Strong '${query}' tidak ditemukan.`);
  process.exit(1);
}

console.log(JSON.stringify(result, null, 2));
