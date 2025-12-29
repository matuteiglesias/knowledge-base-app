cd ~/Documents/paper-kb   # <- run from project root so python -m src.grobid_ingest resolves
mkdir -p src/xmls

for pdf in src/downloads/*.pdf; do
  echo "---- processing: $pdf ----"
  base=$(basename "$pdf" .pdf)
  # save TEI to src/xmls/<origname>.tei.xml, enable langchain output (--langchain)
  python3 -m src.grobid_ingest "$pdf" --save-tei "src/xmls/${base}.tei.xml" --langchain
  rc=$?
  if [ $rc -ne 0 ]; then
    echo "ERROR processing $pdf (exit $rc). See output above; sleeping 3s and continuing."
    sleep 3
  else
    echo "OK: $pdf -> src/xmls/${base}.tei.xml"
  fi
  # polite throttle (reduce risk of transient errors)
  sleep 1
done
