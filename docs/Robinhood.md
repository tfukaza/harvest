### Robinhood
1. Create a Robinhood account
2. Follow instructions on the robin_stock library [documentation](https://github.com/jmfernandes/robin_stocks/blob/master/Robinhood.rst) to set up 2FA.
3. Create a file called `secret.yaml` in the directory you are running your code, and add the following parameters:
```yaml
robin_mfa:      'YourOTPcode'
robin_username: 'username'
robin_password: 'password'
```