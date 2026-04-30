document.getElementById("btn-verify-pdf").addEventListener("click", async () => {
  const inp = document.getElementById("input-pdf-verify");
  const res = document.getElementById("result-verify");
  res.classList.remove("hidden", "bg-emerald-100", "text-emerald-800", "bg-rose-100", "text-rose-800", "bg-amber-50", "text-amber-900", "bg-red-100", "text-red-800");
  if (!inp.files?.length) {
    res.classList.add("bg-amber-50", "text-amber-900");
    res.textContent = "Seleccione un archivo PDF.";
    return;
  }
  res.classList.add("bg-slate-100", "text-slate-700");
  res.textContent = "Analizando PDF…";
  const fd = new FormData();
  fd.append("file", inp.files[0]);
  try {
    const r = await fetch("/api/verify-pdf", { method: "POST", body: fd });
    const data = await r.json().catch(() => ({}));
    res.classList.remove("bg-slate-100", "text-slate-700");
    if (data.error && !data.time && data.isValid === false) {
      res.classList.add("bg-amber-50", "text-amber-900");
      res.textContent = data.error;
      return;
    }
    if (data.isValid) {
      res.classList.add("bg-emerald-100", "text-emerald-800");
      res.innerHTML = `✅ <strong>Documento auténtico</strong><br><span class="text-xs">Tiempo de verificación: ${Number(data.time || 0).toFixed(4)} s</span>`;
    } else {
      res.classList.add("bg-rose-100", "text-rose-800");
      res.innerHTML = `❌ <strong>No válido o revocado</strong>${data.error ? `<br><span class="text-xs">${data.error}</span>` : ""}<br><span class="text-xs">TV: ${Number(data.time || 0).toFixed(4)} s</span>`;
    }
  } catch {
    res.classList.remove("bg-slate-100", "text-slate-700");
    res.classList.add("bg-red-100", "text-red-800");
    res.textContent = "No se pudo contactar al servidor.";
  }
});
