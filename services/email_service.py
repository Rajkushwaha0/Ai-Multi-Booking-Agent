import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import get_settings
from logger import email_logger


# ------------------------------------------------------------------------------
# Core send function — all other functions in this module call this one.
# Opens a fresh SMTP connection per send, which is safe for low-to-medium volume.
# Returns True on success, False on any failure — never raises to the caller.
# ------------------------------------------------------------------------------

def send_email(to: str, subject: str, html_body: str) -> bool:
    """
    Sends an HTML email over SMTP using STARTTLS.

    Opens a connection, authenticates, sends, and closes — all in one call.
    Any SMTP or network error is caught and logged; the caller gets False.
    This ensures a failed email never crashes a booking or auth flow.
    """
    settings = get_settings()

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = settings.smtp.from_address
        msg["To"]      = to

        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.smtp.host, settings.smtp.port) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.smtp.user, settings.smtp.password)
            server.sendmail(settings.smtp.from_address, to, msg.as_string())

        email_logger.info("Email sent — to=%s subject=%s", to, subject)
        return True

    except smtplib.SMTPAuthenticationError:
        email_logger.error("SMTP authentication failed. Check SMTP_USER and SMTP_PASSWORD.")
        return False

    except smtplib.SMTPException as exc:
        email_logger.error("SMTP error sending to=%s: %s", to, str(exc))
        return False

    except Exception as exc:
        email_logger.error("Unexpected error sending email to=%s: %s", to, str(exc))
        return False


# ------------------------------------------------------------------------------
# Transactional email functions
# Each function composes an HTML template and delegates to send_email().
# ------------------------------------------------------------------------------

def send_otp_email(to: str, otp: str, name: str) -> bool:
    """
    Sends a verification OTP to the user's email address.
    Called at signup and resend-OTP. Valid for 10 minutes.
    """
    subject   = "Your verification code"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 32px; color: #333;">
        <h2 style="margin-bottom: 8px;">Hi {name},</h2>
        <p style="margin-bottom: 24px;">Use the code below to verify your email address.</p>

        <div style="background: #f5f5f5; border-radius: 8px; padding: 24px; text-align: center; margin-bottom: 24px;">
            <span style="font-size: 40px; font-weight: bold; letter-spacing: 12px; color: #111;">{otp}</span>
        </div>

        <p>This code is valid for <strong>10 minutes</strong>. Do not share it with anyone.</p>
        <p style="color: #888; font-size: 13px;">If you did not create an account, you can safely ignore this email.</p>
    </body>
    </html>
    """
    return send_email(to, subject, html_body)


def send_welcome_email(to: str, name: str) -> bool:
    """
    Sent once, immediately after the user successfully verifies their email.
    """
    subject   = "Welcome to Multi Booking Agent"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 32px; color: #333;">
        <h2>Welcome, {name}!</h2>
        <p>Your email has been verified. You are now ready to book movies, cabs, doctor appointments, and restaurants — all in one place.</p>
        <p>Start by completing your profile so we can personalise your experience.</p>
        <p style="margin-top: 32px; color: #888; font-size: 13px;">The Multi Booking Agent Team</p>
    </body>
    </html>
    """
    return send_email(to, subject, html_body)


def send_password_reset_email(to: str, reset_token: str, name: str) -> bool:
    """
    Sends a password reset link containing the reset token.
    The link is valid for 15 minutes — enforced server-side by the Redis TTL.
    """
    subject    = "Reset your password"
    reset_link = f"/auth/reset-password?token={reset_token}"
    html_body  = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 32px; color: #333;">
        <h2>Hi {name},</h2>
        <p>We received a request to reset the password for your account.</p>
        <p>Click the button below to choose a new password. This link expires in <strong>15 minutes</strong>.</p>

        <div style="text-align: center; margin: 32px 0;">
            <a href="{reset_link}"
               style="background-color: #2563eb; color: #fff; padding: 12px 28px;
                      text-decoration: none; border-radius: 6px; font-weight: bold;">
                Reset Password
            </a>
        </div>

        <p style="color: #888; font-size: 13px;">
            If you did not request a password reset, please ignore this email.
            Your password will not change.
        </p>
    </body>
    </html>
    """
    return send_email(to, subject, html_body)


def send_booking_confirmed_email(to: str, name: str, booking: dict) -> bool:
    """
    Sent when a booking is successfully confirmed.
    Expects booking keys: seats, datetime, pass_key.
    Any missing key renders as a dash.
    """
    subject   = "Booking Confirmed"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 32px; color: #333;">
        <h2>Booking Confirmed, {name}!</h2>
        <p>Here are your booking details:</p>

        <table style="border-collapse: collapse; width: 100%; margin-top: 16px;">
            <tr style="background: #f9f9f9;">
                <td style="padding: 12px 16px; border: 1px solid #e0e0e0; font-weight: bold;">Seats</td>
                <td style="padding: 12px 16px; border: 1px solid #e0e0e0;">{booking.get("seats", "—")}</td>
            </tr>
            <tr>
                <td style="padding: 12px 16px; border: 1px solid #e0e0e0; font-weight: bold;">Date &amp; Time</td>
                <td style="padding: 12px 16px; border: 1px solid #e0e0e0;">{booking.get("datetime", "—")}</td>
            </tr>
            <tr style="background: #f9f9f9;">
                <td style="padding: 12px 16px; border: 1px solid #e0e0e0; font-weight: bold;">Pass Key</td>
                <td style="padding: 12px 16px; border: 1px solid #e0e0e0;">
                    <strong style="font-size: 18px; letter-spacing: 2px;">{booking.get("pass_key", "—")}</strong>
                </td>
            </tr>
        </table>

        <p style="margin-top: 24px; color: #888; font-size: 13px;">
            Show your pass key at the venue. Keep this email for your records.
        </p>
    </body>
    </html>
    """
    return send_email(to, subject, html_body)


def send_booking_failed_email(to: str, name: str, reason: str) -> bool:
    """
    Sent when a booking attempt fails — payment issue, no availability, lock timeout, etc.
    """
    subject   = "Booking Failed"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 32px; color: #333;">
        <h2>Hi {name},</h2>
        <p>Unfortunately, your booking could not be completed.</p>
        <p><strong>Reason:</strong> {reason}</p>
        <p>Please try again or contact support if the issue persists.</p>
        <p style="margin-top: 32px; color: #888; font-size: 13px;">The Multi Booking Agent Team</p>
    </body>
    </html>
    """
    return send_email(to, subject, html_body)


def send_refund_email(to: str, name: str, amount: float) -> bool:
    """
    Sent when a refund has been processed for a cancelled booking.
    """
    subject   = "Refund Processed"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 32px; color: #333;">
        <h2>Hi {name},</h2>
        <p>Your refund of <strong>{amount:.2f}</strong> has been processed successfully.</p>
        <p>Please allow 5–7 business days for the amount to appear in your account, depending on your bank.</p>
        <p style="margin-top: 32px; color: #888; font-size: 13px;">The Multi Booking Agent Team</p>
    </body>
    </html>
    """
    return send_email(to, subject, html_body)
