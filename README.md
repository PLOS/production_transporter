# Production Transporter Plugin

An FTP workflow element for Janeway that deposits articles and their files to an FTP server. The plugin supports both default file transfers (using a default .zip) and custom file transfer functions with callback mechanisms.

## Features

- **Automatic Article Deposit**: Automatically transfers articles to FTP servers when they reach specified workflow stages
- **Multiple Transfer Methods**: Supports both default ZIP file transfers and custom file transfer functions (.zip and .go.xml)
- **Configurable Workflow Integration**: Can be triggered at different stages (Accepted, Submitted, Published)
- **Callback System**: Supports success and failure callbacks for custom transfer functions

## Installation

1. Clone this repository into your `path/to/janeway/src/plugins/` folder
2. Checkout a version that will work with your current Janeway version
3. Install requirements with `pip3 install -r requirements.txt`


Note: when using SFTP the relevant ECDSA key for the server being deposited. You can obtain this by running:

`ssh-keyscan -t ecdsa theserverdomain.com`

## Configuration Settings

### Standard File Transfer
1. Enable "Enable Transport" setting
2. Configure FTP server details (address, username, password, remote path)
3. Set the "Production Manager Stage" to trigger the transfer
4. Optionally configure email notifications

### Custom File Transfer
1. Enable "Enable Transport" and "Enable Transport of Custom Files"
2. Create custom functions for file path generation and callbacks
3. Configure the function paths in the plugin settings

## Custom Function Requirements
Custom functions must follow this signature:
```python
def custom_function(journal_code: str, article_id: str) -> Union[str, None]:
    # Example: resolve the file path using your own logic
    file_path = get_file_path(journal_code, article_id)

    if not file_path:
        return None

    return file_path
```
