# Builtins
from getpass import getpass

# External libraries
import pyotp

# Submodule imports
from harvest.wizard._base import Wizard

class RobinhoodWizard(Wizard):
    """
    A wizard for Robinhood.
    """

    def create_secret(self, path: str) -> bool:
            print("""⚠️  Hmm, looks like you haven't set up login credentials for Robinhood yet.""")

            should_setup = self.get_bool("❓ Do you want to set it up now? (y/n)", persistent=True)

            if not should_setup:
                print("""\n💬 You can't use Robinhood unless we can log you in. You can set up the credentials manually, or use other brokers.""")
                return False

            print("""\n💬 Alright! Let's get started""")

            have_account = self.get_bool("❓ Do you have a Robinhood account? (y/n)", default='y')

            if not have_account:
                self.wait_for_input("""\n💬 In that case you'll first need to make an account. I'll wait here, so hit Enter or Return when you've done that.""")
            
            have_mfa = self.get_bool("❓ Do you have Two Factor Authentication enabled? (y/n)", default='y')

            if not have_mfa:
                print("""\n💬 Robinhood (and Harvest) requires users to have 2FA enabled, so we'll turn that on next.""")
            else:
                self.wait_for_input("""\n💬 We'll need to reconfigure 2FA to use Harvest, so temporarily disable 2FA. Hit Enter when you're ready.""")

            self.wait_for_input("""💬 Now enable 2FA. Robinhood should ask you what authentication method you want to use.""")
            self.wait_for_input("💬 Select 'Authenticator App'. (hit Enter)")
            self.wait_for_input("💬 Select 'Can't scan'. (hit Enter)")

            mfa = self.get_string("""❓ You should see a string of letters and numbers on the screen. Type it in here and press Enter:\n""", pattern=r'[\d\w]+')

            while True:
                try:
                    totp = pyotp.TOTP(mfa).now()
                except:
                    print("\n😮 Woah! Something went wrong. Make sure you typed in the code correctly.")
                    # mfa = input("""❓ Try typing in the code again:\n""")
                    mfa = self.get_string("\n😮 Woah! Something went wrong. Make sure you typed in the code correctly.", pattern=r'[\d\w]+')
                    continue
                break

            print(f"""💬 Good! Robinhood should now be asking you for a 6-digit passcode. Type in: {totp} ---""")
            print(f"""⚠️  Beware, this passcode expires in a few seconds! If you couldn't type it in time, it should be regenerated.""")

            new_passcode = True

            while new_passcode:
                new_passcode = self.get_bool("""❓ Do you want to generate a new passcode? (y/n)[n]""", default='n')

                if new_passcode:
                    totp  = pyotp.TOTP(mfa).now()
                    print(f"\n💬 New passcode: {totp} ---")
                else:
                    break

            self.wait_for_input("""\n💬 Robinhood will show you a backup code. This is useful when 2FA fails, so make sure to keep it somewhere safe. (Enter)""")
            self.wait_for_input("""💬 It is recommended you also set up 2FA using an app like Authy or Google Authenticator, so you don't have to run this setup wizard every time you log into Robinhood. (Enter)""")
            print(f"""💬 Open an authenticator app of your choice, and use the MFA code you typed in earlier to set up OTP passcodes for Robinhood:\n---------------\n{mfa}\n---------------""")
            self.wait_for_input("Press Enter when you're ready.")

            print(f"""💬 Almost there! Type in your username and password for Robinhood""")

            username = self.get_string("\n❓ Username: ")
            password = self.get_password("❓ Password: "))

            print(f"""\n💬 All steps are complete now 🎉. Generating secret.yml...""")

            d = {
                'robin_mfa':      f"{mfa}",
                'robin_username': f"{username}",
                'robin_password': f"{password}"
            }

            with open(path, 'w') as file:
                yml = yaml.dump(d, file)
            
            print(f"""💬 secret.yml has been created! Make sure you keep this file somewhere secure and never share it with other people.""")
            
            return True 