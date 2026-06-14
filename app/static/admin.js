function previewKeywordImport(text) {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const seen = new Set();
  let duplicate = 0;
  const fresh = [];
  for (const line of lines) {
    if (seen.has(line)) {
      duplicate += 1;
    } else {
      seen.add(line);
      fresh.push(line);
    }
  }
  return { total: lines.length, fresh, duplicate };
}

window.previewKeywordImport = previewKeywordImport;
