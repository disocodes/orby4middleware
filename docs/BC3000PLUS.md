# Mindray BC-3000 Plus profile

The BC-3000 Plus is included as the first model-specific legacy hematology profile.

## Intended transport
A site normally connects the analyzer's host serial port to an edge PC using the correct RS-232
cable/adapter. The edge helper supports ENQ/ACK/EOT style session control and forwards the complete
message body to the BC-3000 Plus parser.

Serial defaults vary by configuration/firmware. Never assume settings without checking the analyzer
and its operation/communication manual.

## Safety
The parser is marked `vendor-documented` rather than `validated-lab`. Before clinical use, capture
real de-identified/QC frames from the exact instrument and compare every field boundary, decimal,
unit and flag against the analyzer printout and vendor documentation.
