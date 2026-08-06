<?php
/**
 * Contoh: cari satu entri Strong's berdasarkan nomornya.
 * Jalankan: php lookup.php H430
 *
 * Cocok dipakai sebagai referensi integrasi ke proyek CodeIgniter 4
 * (mis. Church Center) -- cukup baca file JSON combined sebagai
 * data statis, atau import ke tabel MySQL jika perlu query lebih rumit.
 */

$dictionaryPath = __DIR__ . '/../../data/combined/strongs-full.json';
$dictionary = json_decode(file_get_contents($dictionaryPath), true);

function lookup(array $dictionary, string $strongNumber): ?array
{
    foreach ($dictionary as $entry) {
        if ($entry['strong_number'] === $strongNumber) {
            return $entry;
        }
    }
    return null;
}

$query = $argv[1] ?? 'H430';
$result = lookup($dictionary, $query);

if ($result === null) {
    echo "Nomor Strong '{$query}' tidak ditemukan." . PHP_EOL;
    exit(1);
}

echo json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE) . PHP_EOL;
