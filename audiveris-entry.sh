#!/bin/sh
set -e

# Test JPod usage by trying to load the first page
is_jpod_ok() {
  java -cp "/opt/audiveris/lib/*" \
       de.intarsys.pdf.content.CSInterpreter 2>/dev/null
  # If it doesn't crash outright regarding native freetype,
  # we assume JPod is available. This is a rough check.
}

# Process a file with Audiveris
process_with_audiveris() {
  input_file="$1"
  shift
  cd /data && audiveris "$input_file" "$@"
}

# Handle PDF files
handle_pdf() {
  pdf_file="$1"
  shift
  
  if is_jpod_ok; then
    echo "JPod detection -> OK. Running Audiveris on PDF."
    process_with_audiveris "$pdf_file" "$@"
  else
    echo "JPod detection -> NOT available. Converting PDF to TIFF..."
    tiff_file="${pdf_file%.pdf}.tiff"
    convert -density 300 "$pdf_file" -colorspace Gray "$tiff_file"
    echo "Now running Audiveris on TIFF."
    process_with_audiveris "$tiff_file" "$@"
    # Clean up the temporary TIFF file
    rm -f "$tiff_file"
  fi
}

# Main entry point
if [ "$1" = "api" ]; then
    cd /app/api && uvicorn api:app --host 0.0.0.0 --port 8000
else
    case "$1" in
        *.pdf)
            handle_pdf "$@"
            ;;
        *)
            process_with_audiveris "$@"
            ;;
    esac
fi 