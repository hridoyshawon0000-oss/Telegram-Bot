def schedule_message_deletion(chat_id, message_id, delay_seconds=None):
    if delay_seconds is None:
        delay_seconds = get_delete_after()

    delete_at = time.time() + delay_seconds

    with closing(db_connect()) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO scheduled_deletions
                (chat_id, message_id, delete_at)
            VALUES (?, ?, ?)
            """,
            (chat_id, message_id, delete_at),
        )
        conn.commit()
        async def copy_to_user(
    application,
    user_id,
    source_chat_id,
    message_id,
    reply_markup=None,
    deletion_seconds=None,
):
    for attempt in range(MAX_RETRIES):
        try:
            sent = await application.bot.copy_message(
                chat_id=user_id,
                from_chat_id=source_chat_id,
                message_id=message_id,
                reply_markup=reply_markup,
            )

            schedule_message_deletion(
                user_id,
                sent.message_id,
                delay_seconds=deletion_seconds,
            )
            return 1

        except RetryAfter as error:
            delay = error.retry_after
            if hasattr(delay, "total_seconds"):
                delay = delay.total_seconds()
            await asyncio.sleep(float(delay) + 1)

        except Forbidden:
            mark_user_blocked(user_id)
            raise

        except TelegramError:
            if attempt == MAX_RETRIES - 1:
                raise
            await asyncio.sleep(attempt + 1)

    return 0
    async def scan_old_media_and_podcasts_pyrogram():
    welcome_count = 0
    podcast_count = 0

    async with PyrogramClient(
        "BQG2RvEAMqEZvxYVQSiqGgYnAD2bpddJ_Lez9m0iqkT_2NuFZxGCUEMp5fWuGMJuKk9nMy7OAk55brZMGQElagVIt0P1jOmxnu8EymXtZgZzk8lHupdjcHNsJYIezihx6RGPry_aNDGl_dLP1KlRbZ_KEAZk7NUw6GsX_-RUXHWQPtaLmfS7qH987xKAiGiVo7pBjVGyL7F9kZVxHFBKMwq9nHbOT3T5SGxfljYWh3Ntq-6VAfdznvqVyztz6CvZS1UvjEQPfewL4qgKqqbx5lT8d0adu-8uuC6FtaboN6GEVgVIetDC1lU1i7cAKh-wXOgFTLHLlDhqF6PXPzyxnqlmwMTU9wAAAAIL2oKZAA",
        api_id=33511945,
        api_hash=d044392a17690c14ee5b4a23651a0700,
        session_string=STRING_SESSION,
    ) as pyro_app:

        logger.info("Scanning old media from target channel...")

        try:
            chat_obj = await pyro_app.get_chat(
                PODCAST_SOURCE_CHANNEL_ID
            )
            target_chat_id = chat_obj.id

        except Exception as error:
            raise RuntimeError(
                f"Cannot access source channel: {error}"
            ) from error

        async for message in pyro_app.get_chat_history(
            target_chat_id
        ):
            media_type = None

            if message.photo:
                media_type = "photo"

            elif message.video:
                media_type = "video"

            if media_type:
                file_id = (
                    message.photo.file_id
                    if media_type == "photo"
                    else message.video.file_id
                )

                if save_welcome_media(
                    media_type,
                    file_id,
                    message.id,
                ):
                    welcome_count += 1

            is_video = bool(message.video) or bool(
                message.document
                and message.document.mime_type
                and message.document.mime_type.startswith("video/")
            )

            if is_video:
                with closing(db_connect()) as conn:
                    cursor = conn.execute(
                        """
                        INSERT OR IGNORE INTO podcast_videos
                            (chat_id, message_id, added_at)
                        VALUES (?, ?, ?)
                        """,
                        (
                            target_chat_id,
                            message.id,
                            time.time(),
                        ),
                    )
                    conn.commit()

                    if cursor.rowcount > 0:
                        podcast_count += 1

    logger.info(
        "Scan complete. New welcome media: %s, new videos: %s",
        welcome_count,
        podcast_count,
    )

    return welcome_count, podcast_count
    async def podcast_poster_worker(application: Application):
    await asyncio.sleep(20)

    while True:
        try:
            with closing(db_connect()) as conn:
                videos = conn.execute(
                    """
                    SELECT chat_id, message_id
                    FROM podcast_videos
                    ORDER BY RANDOM()
                    LIMIT 15
                    """
                ).fetchall()

            users = get_registered_users()

            if videos and users:
                logger.info(
                    "Sending %s videos to %s users.",
                    len(videos),
                    len(users),
                )

                for chat_id, msg_id in videos:
                    for (user_id,) in users:
                        try:
                            await copy_to_user(
                                application=application,
                                user_id=user_id,
                                source_chat_id=chat_id,
                                message_id=msg_id,
                                reply_markup=PODCAST_BUTTON,
                                deletion_seconds=30 * 60,
                            )

                            await asyncio.sleep(0.05)

                        except Exception as error:
                            logger.warning(
                                "Video %s failed for user %s: %s",
                                msg_id,
                                user_id,
                                error,
                            )

            else:
                logger.info(
                    "No videos or registered users available."
                )

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception("Podcast worker error.")

        await asyncio.sleep(30 * 60)
        async def importpodcast_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message

    if not user or not message or not is_admin(user.id):
        if message:
            await message.reply_text("⛔ Admin access only.")
        return

    status_msg = await message.reply_text(
        "⏳ Scanning old videos. Please wait..."
    )

    try:
        welcome_added, videos_added = (
            await scan_old_media_and_podcasts_pyrogram()
        )

        with closing(db_connect()) as conn:
            total_welcome = conn.execute(
                "SELECT COUNT(*) FROM welcome_media"
            ).fetchone()[0]

            total_videos = conn.execute(
                "SELECT COUNT(*) FROM podcast_videos"
            ).fetchone()[0]

        await status_msg.edit_text(
            "✅ Scan completed!\n\n"
            f"🖼️ New welcome media: {welcome_added}\n"
            f"🎬 New videos found: {videos_added}\n"
            f"📦 Total welcome media: {total_welcome}\n"
            f"🎥 Total saved videos: {total_videos}"
        )

    except Exception as error:
        logger.exception("Video scan failed.")

        await status_msg.edit_text(
            f"❌ Scan failed: {str(error)[:800]}"
        )
        
