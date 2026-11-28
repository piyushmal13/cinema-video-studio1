import asyncio
import json
import os
import subprocess
import tempfile
import unittest
import urllib.parse
from unittest.mock import Mock, patch

from edge_tts.exceptions import NoAudioReceived

from scripts import generate_assets
from scripts import setup_real_audio

VALID_NARRATION = (
    "Across this short film, viewers get clear context before reaching the conclusion. "
    "The opening frames the question, then separates known information from assumptions. "
    "Each section explains one step and shows how the ideas connect. "
    "A practical example makes the process easier to follow without inventing statistics. "
    "The ending highlights the main takeaway and a careful next question. "
    "The script avoids unsupported claims and keeps the reasoning direct, understandable, "
    "and specific to the requested topic."
)


class GenerateAssetsTests(unittest.TestCase):
    @staticmethod
    def _scenes(count):
        return [
            {
                "type": "cinema_hero",
                "weight": 1,
                "kicker": f"BEAT {index}",
                "headline": f"Scene {index}",
                "visualQuery": "cinematic ocean waves at night",
                "cameraMotion": "zoom_in",
                "sfxCue": "whoosh",
            }
            for index in range(count)
        ]

    def test_ffmpeg_synthesizes_decodable_phonk_and_cinema_scores(self):
        ffmpeg = generate_assets._ffmpeg_executable()
        with tempfile.TemporaryDirectory() as temp_dir:
            for style in ("phonk", "cinema"):
                path = os.path.join(temp_dir, f"{style}.mp3")
                generate_assets.synthesize_ambient_cinema_score(8, path, [], style)
                self.assertGreater(os.path.getsize(path), 1000)
                subprocess.run(
                    [ffmpeg, "-v", "error", "-i", path, "-f", "null", "-"],
                    check=True,
                    capture_output=True,
                )

    def test_ffmpeg_synthesizes_decodable_transition_sfx(self):
        ffmpeg = generate_assets._ffmpeg_executable()
        with tempfile.TemporaryDirectory() as temp_dir:
            assets_dir = os.path.join(temp_dir, "assets")
            output_dir = os.path.join(temp_dir, "public")
            with patch.dict(
                os.environ,
                {"CINEMA_AUDIO_ASSET_DIR": assets_dir},
            ):
                generate_assets.synthesize_transition_sfx(output_dir)
            for variants in setup_real_audio.SFX_VARIANTS.values():
                for filename in variants:
                    path = os.path.join(output_dir, filename)
                    self.assertGreater(os.path.getsize(path), 1000)
                    subprocess.run(
                        [ffmpeg, "-v", "error", "-i", path, "-f", "null", "-"],
                        check=True,
                        capture_output=True,
                    )

    def test_sfx_cue_variants_cycle_without_repeating_the_same_file(self):
        scene = {"sfxCue": "whoosh", "headline": "A changing market"}
        selected = {
            generate_assets._sfx_variant_filename(scene, index)
            for index in range(3)
        }
        self.assertEqual(selected, set(setup_real_audio.SFX_VARIANTS["whoosh"]))

    def test_master_mix_uses_different_sfx_variants_for_repeated_cues(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            asset_dir = os.path.join(temp_dir, "assets")
            output_path = os.path.join(temp_dir, "master.mp3")
            setup_real_audio.generate_audio_assets(asset_dir, duration=12)

            def fake_ffmpeg(command, **kwargs):
                with open(output_path, "wb") as audio_file:
                    audio_file.write(b"mixed audio")
                return Mock(returncode=0)

            with (
                patch.dict(os.environ, {"CINEMA_AUDIO_ASSET_DIR": asset_dir}),
                patch.object(generate_assets.subprocess, "run", side_effect=fake_ffmpeg) as run,
            ):
                generate_assets.mix_final_audio(
                    "voice.mp3",
                    "score.mp3",
                    output_path,
                    [
                        {"startSec": 0, "sfxCue": "whoosh", "headline": "Opening"},
                        {"startSec": 2, "sfxCue": "whoosh", "headline": "Same cue"},
                        {"startSec": 4, "sfxCue": "whoosh", "headline": "Same cue"},
                        {"startSec": 6, "sfxCue": "whoosh", "headline": "Same cue"},
                    ],
                    8,
                )

        command = run.call_args.args[0]
        effect_files = [
            os.path.basename(command[index + 1])
            for index, value in enumerate(command[:-1])
            if value == "-i" and os.path.basename(command[index + 1]).startswith("sfx_whoosh")
        ]
        self.assertEqual(len(setup_real_audio.SFX_VARIANTS["whoosh"]), len(set(effect_files)))

    def test_voiceover_silence_trim_shortens_audio_and_retimes_words(self):
        ffmpeg = generate_assets._ffmpeg_executable()
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "voiceover.mp3")
            subprocess.run(
                [
                    ffmpeg, "-y",
                    "-f", "lavfi", "-t", "0.5", "-i",
                    "anullsrc=channel_layout=mono:sample_rate=44100",
                    "-f", "lavfi", "-t", "2", "-i",
                    "sine=frequency=440:sample_rate=44100",
                    "-f", "lavfi", "-t", "0.5", "-i",
                    "anullsrc=channel_layout=mono:sample_rate=44100",
                    "-filter_complex", "[0:a][1:a][2:a]concat=n=3:v=0:a=1[a]",
                    "-map", "[a]", "-c:a", "libmp3lame", "-b:a", "96k", path,
                ],
                check=True,
                capture_output=True,
            )
            initial_duration = generate_assets._audio_duration_seconds(path)
            source_words = [
                {"word": f"word{index}", "start": index * 0.3, "end": (index + 1) * 0.3}
                for index in range(8)
            ]

            words, trimmed_duration = generate_assets.trim_voiceover_silence(
                path, source_words
            )

        self.assertLess(trimmed_duration, initial_duration - 0.25)
        self.assertGreater(trimmed_duration, 1.5)
        self.assertEqual(len(words), len(source_words))
        self.assertLessEqual(words[-1]["end"], trimmed_duration)

    def test_pollinations_requests_json_mode(self):
        scenes = [
            {
                "type": "cinema_hero",
                "weight": 0.2,
                "kicker": "OPENING",
                "headline": f"Scene {index}",
                "visualQuery": "cinematic ocean waves at night",
                "cameraMotion": "zoom_in",
                "sfxCue": "whoosh",
            }
            for index in range(5)
        ]
        storyboard = {
            "narration": VALID_NARRATION,
            "scenes": scenes,
        }
        response = Mock(
            status_code=200,
            json=lambda: {
                "choices": [{"message": {"content": json.dumps(storyboard)}}]
            },
        )

        with (
            patch.object(generate_assets, "GEMINI_API_KEY", "test-gemini-key"),
            patch.dict(os.environ, {"PREFER_GEMINI": "0"}),
            patch.object(generate_assets.requests, "post", return_value=response) as post,
        ):
            result = generate_assets.generate_storyboard("A test prompt", "A test system prompt", 5)

        self.assertEqual(result["narration"], storyboard["narration"])
        self.assertEqual(result["scenes"], storyboard["scenes"])
        self.assertEqual(result["storyboardProvider"], "pollinations:openai")
        self.assertEqual(post.call_args.args[0], "https://text.pollinations.ai/openai")
        self.assertEqual(post.call_args.kwargs["json"]["response_format"], {"type": "json_object"})
        self.assertEqual(post.call_args.kwargs["json"]["max_tokens"], 8192)

    def test_pollinations_accepts_sixteen_scenes_and_trims_to_fourteen(self):
        storyboard = {
            "narration": VALID_NARRATION,
            "scenes": self._scenes(16),
        }
        response = Mock(
            status_code=200,
            json=lambda: {
                "choices": [{"message": {"content": json.dumps(storyboard)}}]
            },
        )

        with (
            patch.object(generate_assets, "GEMINI_API_KEY", ""),
            patch.object(generate_assets.requests, "post", return_value=response),
        ):
            result = generate_assets.generate_storyboard(
                "A focused film about gold-market liquidity", "system", 5
            )

        self.assertEqual(len(result["scenes"]), 14)
        self.assertAlmostEqual(sum(scene["weight"] for scene in result["scenes"]), 1.0)

    def test_provider_errors_use_deterministic_storyboard_fallback(self):
        malformed = Mock(
            status_code=200,
            json=lambda: {"choices": [{"message": {"content": "not valid JSON"}}]},
        )
        service_unavailable = Mock(status_code=503, text="temporarily unavailable")
        rate_limited = Mock(status_code=429, text="try again later")

        with (
            patch.object(generate_assets, "GEMINI_API_KEY", "test-gemini-key"),
            patch.dict(os.environ, {"PREFER_GEMINI": "0"}),
            patch.object(
                generate_assets.requests,
                "post",
                side_effect=[
                    malformed,
                    malformed,
                    service_unavailable,
                    rate_limited,
                    service_unavailable,
                ],
            ),
            patch.object(generate_assets.time, "sleep"),
        ):
            result = generate_assets.generate_storyboard(
                "Explain how gold-market liquidity works",
                "system",
                75,
                brand="IFXTRADES",
                color="#D4AF37",
                mode="shorts",
                is_hinglish=False,
            )

        self.assertGreaterEqual(len(result["narration"].split()), 75)
        self.assertGreaterEqual(len(result["scenes"]), 5)
        self.assertLessEqual(len(result["scenes"]), 6)
        self.assertAlmostEqual(sum(scene["weight"] for scene in result["scenes"]), 1.0)
        self.assertIn("gold-market liquidity", result["narration"].lower())
        self.assertTrue(result.get("degradedMode"))
        self.assertEqual(len({scene["visualQuery"] for scene in result["scenes"]}), len(result["scenes"]))

    def test_deterministic_fallback_supports_hinglish_and_runtime_word_target(self):
        result = generate_assets.build_fallback_storyboard(
            "Aaj gold market ko samjhao",
            "IFXTRADES",
            "#D4AF37",
            "shorts",
            True,
            min_words=150,
        )

        self.assertGreaterEqual(len(result["narration"].split()), 150)
        self.assertIn("Aaj ka market brief", result["narration"])
        self.assertGreaterEqual(len(result["scenes"]), 5)
        self.assertLessEqual(len(result["scenes"]), 6)

    def test_edge_no_audio_retries_voices_then_uses_gtts_with_word_timings(self):
        class NoAudioCommunicate:
            async def stream(self):
                raise NoAudioReceived()
                yield {}

        class FakeGTTS:
            def __init__(self, text, lang):
                self.text = text
                self.lang = lang

            def save(self, path):
                with open(path, "wb") as audio_file:
                    audio_file.write(b"mock mp3 bytes")

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "voiceover.mp3")
            with (
                patch.object(
                    generate_assets.edge_tts,
                    "Communicate",
                    side_effect=lambda *args, **kwargs: NoAudioCommunicate(),
                ) as communicate,
                patch.object(generate_assets, "gTTS", side_effect=FakeGTTS) as gtts,
                patch.object(generate_assets, "_audio_duration_seconds", return_value=3.0),
            ):
                words, duration = asyncio.run(
                    generate_assets.synthesize_voice_and_timings(
                        "**Clear process** [pause] turns 🚀 noise into signal.",
                        "en-US-AndrewMultilingualNeural",
                        output_path,
                    )
                )
                self.assertTrue(os.path.isfile(output_path))

        self.assertEqual(
            [call.args[1] for call in communicate.call_args_list],
            [
                "en-US-AndrewMultilingualNeural",
                "en-US-GuyNeural",
                "en-US-ChristopherNeural",
                "en-GB-RyanNeural",
            ],
        )
        self.assertEqual(gtts.call_args.kwargs, {
            "text": "Clear process turns noise into signal.",
            "lang": "en",
        })
        self.assertEqual(len(words), 6)
        self.assertEqual(duration, 3.0)

    def test_hindi_edge_voice_fallbacks_reach_gtts_in_hindi_mode(self):
        class NoAudioCommunicate:
            async def stream(self):
                raise NoAudioReceived()
                yield {}

        class FakeGTTS:
            def __init__(self, text, lang):
                self.language = lang

            def save(self, path):
                with open(path, "wb") as audio_file:
                    audio_file.write(b"mock mp3 bytes")

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(
                    generate_assets.edge_tts,
                    "Communicate",
                    side_effect=lambda *args, **kwargs: NoAudioCommunicate(),
                ) as communicate,
                patch.object(generate_assets, "gTTS", side_effect=FakeGTTS) as gtts,
                patch.object(generate_assets, "_audio_duration_seconds", return_value=2.0),
            ):
                words, _ = asyncio.run(
                    generate_assets.synthesize_voice_and_timings(
                        "Namaste duniya, aaj seekhte hain.",
                        "hi-IN-SwaraNeural",
                        os.path.join(temp_dir, "hindi.mp3"),
                    )
                )

        self.assertEqual(
            [call.args[1] for call in communicate.call_args_list],
            ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural", "en-IN-PrabhatNeural"],
        )
        self.assertEqual(gtts.call_args.kwargs["lang"], "hi")
        self.assertEqual(len(words), 5)

    def test_video_generation_uses_pollinations_for_high_impact_scenes(self):
        response = Mock(
            status_code=200,
            content=b"\x00\x00\x00\x20ftyp" + b"x" * 60_000,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "scene.mp4")
            with (
                patch.dict(
                    os.environ,
                    {"CINEMA_MEDIA_CACHE_DIR": os.path.join(temp_dir, "cache")},
                ),
                patch.object(generate_assets.requests, "get", return_value=response) as get,
                patch.object(generate_assets, "_is_valid_mp4", return_value=True),
            ):
                generated = generate_assets.try_generate_ai_video_clip(
                    "A dramatic gold-market visual", 0, "vertical", output_path
                )

            self.assertTrue(generated)
            self.assertTrue(os.path.isfile(output_path))
            self.assertIn("model=wan", get.call_args.args[0])
            self.assertIn("width=480&height=832", get.call_args.args[0])

    def test_video_generation_attempts_any_selected_scene_position(self):
        response = Mock(
            status_code=200,
            content=b"ftyp" + b"x" * 60_000,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "scene.mp4")
            with (
                patch.dict(os.environ, {
                    "CINEMA_MEDIA_CACHE_DIR": os.path.join(temp_dir, "cache"),
                    "CINEMA_VIDEO_CLIP_TIMEOUT": "20",
                }),
                patch.object(generate_assets.requests, "get", return_value=response) as get,
                patch.object(generate_assets, "_is_valid_mp4", return_value=True),
            ):
                generated = generate_assets.try_generate_ai_video_clip(
                    "A meaningful visual for a middle scene", 4, "landscape", output_path
                )
                self.assertTrue(os.path.isfile(output_path))
        self.assertTrue(generated)
        self.assertIn("width=832&height=480", get.call_args.args[0])

    def test_video_generation_uses_zero_gpu_after_pollinations_fails(self):
        response = Mock(status_code=429, content=b"")
        child_result = Mock(returncode=1, stderr="Space unavailable", stdout="")
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "scene.mp4")
            with (
                patch.dict(
                    os.environ,
                    {"CINEMA_MEDIA_CACHE_DIR": os.path.join(temp_dir, "cache")},
                ),
                patch.object(generate_assets.requests, "get", return_value=response),
                patch.object(generate_assets.subprocess, "run", return_value=child_result) as run,
            ):
                generated = generate_assets.try_generate_ai_video_clip(
                    "A dramatic gold-market visual", 2, "landscape", output_path
                )

        self.assertFalse(generated)
        self.assertFalse(os.path.exists(output_path))
        self.assertEqual(run.call_args.kwargs["timeout"] <= 45, True)
        self.assertIn("Lightricks/ltx-video-distilled", run.call_args.args[0])

    def test_zero_gpu_output_is_rejected_if_not_a_valid_mp4(self):
        response = Mock(status_code=429, content=b"")
        child_result = Mock(returncode=0, stderr="", stdout="")
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "scene.mp4")

            def create_invalid_output(*args, **kwargs):
                with open(output_path, "wb") as file:
                    file.write(b"not an mp4")
                return child_result

            with (
                patch.dict(
                    os.environ,
                    {"CINEMA_MEDIA_CACHE_DIR": os.path.join(temp_dir, "cache")},
                ),
                patch.object(generate_assets.requests, "get", return_value=response),
                patch.object(generate_assets.subprocess, "run", side_effect=create_invalid_output),
                patch.object(generate_assets, "_is_valid_mp4", return_value=False),
            ):
                generated = generate_assets.try_generate_ai_video_clip(
                    "A dramatic gold-market visual", 0, "vertical", output_path
                )

        self.assertFalse(generated)
        self.assertFalse(os.path.exists(output_path))

    def test_provider_get_retries_rate_limit_then_succeeds(self):
        limited = Mock(status_code=429, headers={"Retry-After": "1"})
        success = Mock(status_code=200, headers={})
        success.raise_for_status = Mock()
        with (
            patch.object(generate_assets.requests, "get", side_effect=[limited, success]) as get,
            patch.object(generate_assets.time, "sleep") as sleep,
        ):
            result = generate_assets._request_with_retry("https://commons.wikimedia.org/w/api.php")
        self.assertIs(result, success)
        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(1.0)

    def test_provider_get_does_not_retry_permanent_not_found(self):
        missing = Mock(status_code=404, headers={})
        missing.raise_for_status.side_effect = generate_assets.requests.HTTPError("404")
        with (
            patch.object(generate_assets.requests, "get", return_value=missing) as get,
            patch.object(generate_assets.time, "sleep") as sleep,
            self.assertRaises(generate_assets.requests.HTTPError),
        ):
            generate_assets._request_with_retry("https://commons.wikimedia.org/missing")
        get.assert_called_once()
        sleep.assert_not_called()

    def test_wikimedia_uses_only_topic_matched_public_domain_or_cc0_photos(self):
        flux = Mock(status_code=503, content=b"", headers={"Content-Type": "text/plain", "Retry-After": "0"})
        pages = {
            "1": {
                "title": "File:Gold bars in a vault.jpg",
                "imageinfo": [{
                    "thumburl": "https://commons.example/gold.jpg",
                    "extmetadata": {"LicenseShortName": {"value": "CC0"}},
                }],
            },
            "2": {
                "title": "File:Gold market illustration.jpg",
                "imageinfo": [{
                    "thumburl": "https://commons.example/illustration.jpg",
                    "extmetadata": {"LicenseShortName": {"value": "Public domain"}},
                }],
            },
        }
        photo = Mock(
            content=b"\xff\xd8" + b"x" * 6000,
            headers={"Content-Type": "image/jpeg"},
        )
        photo.raise_for_status = Mock()
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            os.chdir(temp_dir)
            try:
                with (
                    patch.object(generate_assets, "_commons_pages", return_value=pages),
                    patch.object(generate_assets, "try_archive_org_video", return_value=False),
                    patch.object(generate_assets, "try_wikimedia_video", return_value=False),
                    patch.object(generate_assets.requests, "get", side_effect=[flux, flux, flux, photo]),
                ):
                    result = generate_assets.fetch_broll_or_ai_visual(
                        "gold bars in a vault", 1, "vertical"
                    )
                self.assertEqual(result, ("media/scene_1_photo.jpg", "image"))
                self.assertTrue(os.path.isfile("public/media/scene_1_photo.jpg"))
            finally:
                os.chdir(original_dir)

    def test_archive_video_requires_reusable_rights_and_trims_bounded_file(self):
        search = Mock()
        search.json.return_value = {"response": {"docs": [{"identifier": "gold-film"}]}}
        search.raise_for_status = Mock()
        metadata = Mock()
        metadata.json.return_value = {
            "metadata": {
                "licenseurl": "https://creativecommons.org/publicdomain/zero/1.0/"
            },
            "files": [{"name": "gold-market.mp4", "size": "1200000"}],
        }
        metadata.raise_for_status = Mock()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "scene.mp4")
            with (
                patch.object(generate_assets.requests, "get", side_effect=[search, metadata]),
                patch.object(generate_assets, "_download_bounded", return_value=True),
                patch.object(generate_assets, "_trim_video_clip", return_value=True) as trim,
            ):
                result = generate_assets.try_archive_org_video(
                    "gold market at night", 0, "vertical", output_path
                )

        self.assertTrue(result)
        trim.assert_called_once()

    def test_flux_prompt_locks_topic_and_rejects_non_photographic_outputs(self):
        image = Mock(
            status_code=200,
            content=b"\xff\xd8" + b"x" * 6000,
            headers={"Content-Type": "image/jpeg"},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            os.chdir(temp_dir)
            try:
                with (
                    patch.object(generate_assets, "try_archive_org_video", return_value=False),
                    patch.object(generate_assets, "try_wikimedia_video", return_value=False),
                    patch.object(generate_assets.requests, "get", return_value=image) as get,
                ):
                    result = generate_assets.fetch_broll_or_ai_visual(
                        "gold bars vault", 2, "vertical"
                    )
            finally:
                os.chdir(original_dir)

        self.assertEqual(result, ("media/scene_2.jpg", "image"))
        prompt = urllib.parse.unquote(get.call_args.args[0])
        self.assertIn("gold, bars, vault", prompt)
        self.assertIn("NO anime", prompt)
        self.assertIn("NO random portrait", prompt)

    def test_visual_fetch_reuses_cached_image_without_calling_providers(self):
        image = Mock(
            status_code=200,
            content=b"\xff\xd8" + b"x" * 6000,
            headers={"Content-Type": "image/jpeg"},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            os.chdir(temp_dir)
            try:
                with (
                    patch.dict(
                        os.environ,
                        {
                            "CINEMA_MEDIA_CACHE_DIR": os.path.join(temp_dir, "cache"),
                            "CINEMA_OFFLINE": "",
                        },
                    ),
                    patch.object(generate_assets, "try_archive_org_video", return_value=False),
                    patch.object(generate_assets, "try_wikimedia_video", return_value=False),
                    patch.object(generate_assets.requests, "get", return_value=image) as get,
                ):
                    first = generate_assets.fetch_broll_or_ai_visual(
                        "cinematic gold bars in a vault", 1, "vertical"
                    )
                    second = generate_assets.fetch_broll_or_ai_visual(
                        "CINEMATIC gold bars in a vault", 4, "vertical"
                    )
            finally:
                os.chdir(original_dir)

        self.assertEqual(first, ("media/scene_1.jpg", "image"))
        self.assertEqual(second, ("media/scene_4_cached.jpg", "image"))
        get.assert_called_once()

    def test_audio_vault_is_small_and_all_stems_decode(self):
        ffmpeg = generate_assets._ffmpeg_executable()
        with tempfile.TemporaryDirectory() as temp_dir:
            tracks = setup_real_audio.generate_audio_assets(temp_dir, duration=12)
            self.assertLess(
                sum(os.path.getsize(path) for path in tracks),
                5 * 1024 * 1024,
            )
            for path in tracks:
                subprocess.run(
                    [ffmpeg, "-v", "error", "-i", path, "-f", "null", "-"],
                    check=True,
                    capture_output=True,
                )

    def test_pollinations_free_limit_is_reported_without_retrying_other_models(self):
        response = Mock(
            status_code=402,
            text='{"error":{"code":"FREE_LIMIT","message":"Retry after 35s"}}',
        )

        with (
            patch.object(generate_assets, "GEMINI_API_KEY", ""),
            patch.object(generate_assets.requests, "post", side_effect=[response, response]) as post,
            patch.object(generate_assets.time, "sleep") as sleep,
        ):
            result = generate_assets.generate_storyboard(
                "A test prompt", "A test system prompt", 5
            )

        self.assertEqual(post.call_count, 1)
        sleep.assert_not_called()
        self.assertGreaterEqual(len(result["narration"].split()), 60)
        self.assertTrue(result.get("degradedMode"))
        self.assertEqual(len(result["scenes"]), 6)

    def test_short_storyboard_is_retried_with_an_explicit_minimum(self):
        scenes = [
            {
                "type": "cinema_hero",
                "weight": 0.2,
                "kicker": "OPENING",
                "headline": f"Scene {index}",
                "visualQuery": "cinematic ocean waves at night",
                "cameraMotion": "zoom_in",
                "sfxCue": "whoosh",
            }
            for index in range(5)
        ]
        short_response = Mock(
            status_code=200,
            json=lambda: {
                "choices": [{
                    "message": {
                        "content": json.dumps({"narration": "Too short.", "scenes": scenes})
                    }
                }]
            },
        )
        valid_storyboard = {
            "narration": VALID_NARRATION,
            "scenes": scenes,
        }
        valid_response = Mock(
            status_code=200,
            json=lambda: {
                "choices": [{
                    "message": {"content": json.dumps(valid_storyboard)}
                }]
            },
        )

        with (
            patch.object(generate_assets, "GEMINI_API_KEY", ""),
            patch.object(generate_assets.requests, "post", side_effect=[short_response, valid_response]) as post,
            patch.object(generate_assets.time, "sleep") as sleep,
        ):
            result = generate_assets.generate_storyboard("A test prompt", "A test system prompt", 5)

        self.assertEqual(result["narration"], valid_storyboard["narration"])
        self.assertEqual(result["scenes"], valid_storyboard["scenes"])
        self.assertEqual(result["storyboardProvider"], "pollinations:openai")
        self.assertEqual(post.call_count, 2)
        self.assertIn("at least 60 narration words", post.call_args_list[1].kwargs["json"]["messages"][1]["content"])
        sleep.assert_not_called()

    def test_gemini_falls_through_model_variants_when_free_tier_limited(self):
        scenes = [
            {
                "type": "cinema_hero",
                "weight": 0.2,
                "kicker": "OPENING",
                "headline": f"Scene {index}",
                "visualQuery": "cinematic ocean waves at night",
                "cameraMotion": "zoom_in",
                "sfxCue": "whoosh",
            }
            for index in range(5)
        ]
        storyboard = {
            "narration": VALID_NARRATION,
            "scenes": scenes,
        }
        limited = Mock(
            status_code=402,
            text='{"error":{"code":"FREE_LIMIT","message":"Retry after 35s"}}',
        )
        gemini = Mock(
            status_code=200,
            json=lambda: {
                "candidates": [{
                    "content": {"parts": [{"text": json.dumps(storyboard)}]}
                }]
            },
        )

        with (
            patch.object(generate_assets, "GEMINI_API_KEY", "test-gemini-key"),
            patch.object(generate_assets.requests, "post", side_effect=[limited, limited, gemini]) as post,
            patch.object(generate_assets.time, "sleep"),
        ):
            result = generate_assets.generate_storyboard("A test prompt", "A test system prompt", 5)

        self.assertEqual(result["narration"], storyboard["narration"])
        self.assertEqual(result["scenes"], storyboard["scenes"])
        self.assertEqual(result["storyboardProvider"], "gemini:gemini-3.6-flash")
        self.assertEqual(
            [call.args[0] for call in post.call_args_list],
            [
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent",
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent",
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent",
            ],
        )
        self.assertEqual(
            post.call_args_list[2].kwargs["headers"]["x-goog-api-key"],
            "test-gemini-key",
        )


if __name__ == "__main__":
    unittest.main()
