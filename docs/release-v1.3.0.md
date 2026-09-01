# NetConfigLint v1.3.0

NetConfigLint v1.3.0 is a desktop-layout, readability, and interaction repair release. The
analyzer contract and conservative Huawei diagnostics remain compatible with v1.2.

Highlights:

- Three horizontal, independently resizable cards: analyzed configuration on the left,
  diagnostics in the middle, and temporary editing on the right.
- Visible split handles and spacing keep neighboring cards distinct while preserving drag-based
  resizing at the supported minimum window size.
- ERROR, WARNING, INFO, and UNKNOWN chips replace the diagnostics dropdown and act as toggleable
  filters with an accurate filtered-empty state.
- Mode and vendor controls no longer reserve space for trailing arrows; their selection dialogs
  use consistent opaque Material surfaces, larger text, and bounded option descriptions.
- Both editors now keep titles, subtitles, line status, line-number gutters, placeholder text,
  content, and scrollbars in non-overlapping regions, including long-line horizontal scrolling.
- A unified larger type scale restores clear hierarchy across navigation, cards, dialogs,
  settings, history, diagnostics, and about content.
- Runtime QML regressions verify column order and gaps, editor viewport geometry, long-line
  sizing, clickable severity filters, and dialog bounds in addition to the existing analyzer
  suite.
- Windows x64 portable ZIP runs `NetConfigLint.exe` without opening a console window.

The portable binary is unsigned unless a trusted external Authenticode certificate is supplied.
Static analysis remains conservative and cannot replace vendor-supported validation or lab
testing.
