#!/usr/bin/env python3
import swac

api_url = input("Url: ")
api = swac.api(api_url)

email = input("Email: ")
api.token = api.send_otp(email)

otp = input("OTP: ")
print(api.login(email, otp)["token"])


