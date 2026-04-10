from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from database.models import aiosqlite, DB_PATH
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import io

import asyncio
import time

router = Router()

# Security: Resource Protection
portfolio_semaphore = asyncio.Semaphore(2) # Limit concurrent PDF generations
user_cooldowns = {}
COOLDOWN_SECONDS = 60

def draw_watermark(c, width, height):
    c.saveState()
    c.setFillColorRGB(0.7, 0.7, 0.7, alpha=0.12)  # grey watermark
    c.setFont("Courier-Bold", 80)
    c.translate(width / 2, height / 2)
    c.rotate(45)
    c.drawCentredString(0, 0, "TOP SECRET")
    c.restoreState()


@router.message(Command("portfolio"))
@router.message(F.text == "📄 My Portfolio")
async def cmd_portfolio(message: types.Message):
    user_id = message.from_user.id
    
    # 1. Cooldown Check
    current_time = time.time()
    last_time = user_cooldowns.get(user_id, 0)
    if current_time - last_time < COOLDOWN_SECONDS:
        remaining = int(COOLDOWN_SECONDS - (current_time - last_time))
        await message.answer(f"⏳ Please wait {remaining}s before generating another portfolio.")
        return
    
    user_cooldowns[user_id] = current_time

    # 2. Concurrency Control
    if portfolio_semaphore.locked():
        await message.answer("⚠️ System busy. You are in queue...")

    async with portfolio_semaphore:
        msg = await message.answer("⏳ Generating your professional portfolio...")
        try:

            # =========================
            # Fetch User Data
            # =========================
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
        
                async with db.execute(
                    "SELECT full_name, fake_name, fake_id FROM users WHERE user_id=?",
                    (user_id,)
                ) as cursor:
                    user = await cursor.fetchone()
        
                async with db.execute(
                    "SELECT COUNT(*) FROM posts WHERE user_id=? AND status=?",
                    (user_id, "approved")
                ) as cursor:
                    res = await cursor.fetchone()
                    approved_count = res[0]
        
                async with db.execute("""
                    SELECT category, caption, created_at, content_type
                    FROM posts
                    WHERE user_id=? AND status='approved'
                    ORDER BY created_at DESC
                    LIMIT 20
                """, (user_id,)) as cursor:
                    posts = await cursor.fetchall()
        
            # =========================
            # Generate PDF (Spy Dossier + Watermark)
            # =========================
            buffer = io.BytesIO()
            c = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter
        
            def new_page():
                c.setFillColorRGB(0.05, 0.05, 0.05)
                c.rect(0, 0, width, height, stroke=0, fill=1)
                draw_watermark(c, width, height)
        
            new_page()
        
    # Header
            c.setFillColor(colors.red)
            c.setFont("Courier-Bold", 26)
            c.drawString(50, height - 60, "CLASSIFIED DOSSIER")
            
            # Add Logo (intel.jpg) if exists
            import os
            if os.path.exists("intel.jpg"):
                try:
                    # Draw image at right side
                    c.drawImage("intel.jpg", width - 130, height - 90, width=80, height=80, preserveAspectRatio=True, mask='auto')
                except Exception:
                    pass

            c.setFont("Courier", 12)
            c.drawString(50, height - 85, "TALENT ADDIS INTELLIGENCE FILE")
        
            c.setStrokeColor(colors.red)
            c.setLineWidth(2)
            c.line(50, height - 95, width - 50, height - 95)
        
            # Subject Info
            c.setFillColor(colors.white)
            c.setFont("Courier-Bold", 14)
        
            name = user["full_name"] if user else "UNKNOWN"
            alias = user["fake_name"] if user else "ANONYMOUS"
        
            c.drawString(50, height - 130, f"SUBJECT ALIAS: {alias}")
            c.drawString(50, height - 150, f"STATUS       : ACTIVE")
            c.drawString(50, height - 170, f"APPROVED OPS : {approved_count}")
        
            # Warning Box
            c.setStrokeColor(colors.red)
            c.rect(45, height - 215, width - 90, 80, stroke=1, fill=0)
        
            c.setFont("Courier", 10)
            c.drawString(55, height - 235, "⚠ WARNING")
            c.drawString(55, height - 250, "This document contains classified creative intelligence.")
            c.drawString(55, height - 265, "Unauthorized access or distribution is prohibited.")
        
            # Section Title
            y = height - 310
            c.setFont("Courier-Bold", 16)
            c.setFillColor(colors.red)
            c.drawString(50, y, "OPERATION LOG")
            c.line(50, y - 10, width - 50, y - 10)
        
            # Content
            y -= 40
            c.setFillColor(colors.white)
        
            for idx, post in enumerate(posts, start=1):
                if y < 80:
                    c.showPage()
                    new_page()
                    y = height - 60
        
                category = post["category"]
                date = post["created_at"]
                caption = post["caption"] or "NO DESCRIPTION PROVIDED"
                ctype = post["content_type"]
        
                c.setFont("Courier-Bold", 11)
                c.drawString(50, y, f"[{idx:02}] CATEGORY : {category}")
                y -= 15
        
                c.setFont("Courier", 10)
                c.drawString(50, y, f"DATE      : {date}")
                y -= 15
                c.drawString(50, y, f"TYPE      : {ctype}")
                y -= 15
        
                wrapped = caption[:120] + "..." if len(caption) > 120 else caption
                c.drawString(50, y, f"SUMMARY   : {wrapped}")
        
                y -= 25
                c.setStrokeColor(colors.red)
                c.line(50, y, width - 50, y)
                y -= 20
        
            # Footer
            c.setFont("Courier", 9)
            c.setFillColor(colors.gray)
            c.drawString(50, 40, "END OF FILE — TOP SECRET")
        
            c.save()
            buffer.seek(0)
        
            input_file = BufferedInputFile(
                buffer.read(),
                filename=f"portfolio_{user_id}.pdf"
            )
        
            await message.answer_document(
                document=input_file,
                caption="📄 TOP SECRET portfolio generated."
            )
        
        except Exception as e:
            await msg.edit_text(f"❌ Error generating portfolio: {str(e)}")
        finally:
             try:
                await msg.delete()
             except:
                pass
