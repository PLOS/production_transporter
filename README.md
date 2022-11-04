# production-transporter
An FTP workflow element that will take an accepted article and deposit on an FTP server.

To install:

1. Clone this repository into your path/to/janeway/src/plugins/ folder
2. Checkout a version that will work with your current Janeway version
3. Install requirements with pip3 -r `requirements.txt`

Note: when using SFTP the relevant ECDSA key for the server being deposited. You can obtain this by running:

`ssh-keyscan -t ecdsa theserverdomain.com`