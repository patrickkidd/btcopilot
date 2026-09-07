"""Create a pre-authorized one-time sign-in link: python -m btcopilot.auth.invite <email>"""

import argparse

from btcopilot.app import create_app
from btcopilot.auth.emails import send_invitation
from btcopilot.auth.invitation import Invitation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("--base-url", help="overrides the SITE_URL config")
    parser.add_argument(
        "--send", action="store_true", help="also email the link to the address"
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        email = args.email.strip().lower()
        invitation = Invitation.issue(email, app.config["INVITATION_DAYS"])
        base = (args.base_url or app.config["SITE_URL"]).rstrip("/")
        url = f"{base}/invite/{invitation.token}"
        if args.send:
            send_invitation(email, url)
        print(url)


if __name__ == "__main__":
    main()
