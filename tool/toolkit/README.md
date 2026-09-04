# toolkit — demo tool layer

Local JSON-store CLI demonstrating the agent tool contract. See the spec's
Tool Layer section for the contract; this README's surface table is guarded
by `guards/check-tool-contract.py`.

## Surface

| command | write? |
|---|---|
| list | no |
| get | no |
| search | no |
| create | yes |
| update | yes |
| delete | yes |
| discover | no |
| authcheck | no |

## Usage

python3 tool/toolkit/toolkit.py list
python3 tool/toolkit/toolkit.py create --name example --value 1
