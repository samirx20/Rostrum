// Rostrum's C shim over Signalsmith Stretch 1.3.1 (MIT, LICENSE.txt): planar float buffers, the
// calls src/stretch.rs makes. Not part of upstream.
#include "signalsmith-stretch.h"

using Stretch = signalsmith::stretch::SignalsmithStretch<float>;

extern "C" {

// Seeded: the same input renders the same output on every run (renders are cached and compared).
void *rs_stretch_new(int channels, float sample_rate) {
	auto s = new Stretch(0x5eed);
	s->presetDefault(channels, sample_rate);
	return s;
}
void rs_stretch_free(void *s) { delete static_cast<Stretch *>(s); }
int rs_stretch_input_latency(void *s) { return static_cast<Stretch *>(s)->inputLatency(); }
int rs_stretch_output_latency(void *s) { return static_cast<Stretch *>(s)->outputLatency(); }

// transpose: frequency ratio; tonality_limit: Hz / sample rate above which nothing is transposed (0: none);
// formant: the formant ratio, used when keep_formants (formants then stay put, or move by `formant`, whatever the pitch).
void rs_stretch_set(void *s, float transpose, float tonality_limit, float formant, int keep_formants) {
	auto st = static_cast<Stretch *>(s);
	st->setTransposeFactor(transpose, tonality_limit);
	st->setFormantFactor(keep_formants ? formant : 1.0f, keep_formants != 0);
	st->setFormantBase(0);
}

void rs_stretch_seek(void *s, const float *const *inputs, int input_samples, double rate) {
	static_cast<Stretch *>(s)->seek(inputs, input_samples, rate);
}
void rs_stretch_process(void *s, const float *const *inputs, int input_samples, float *const *outputs, int output_samples) {
	static_cast<Stretch *>(s)->process(inputs, input_samples, outputs, output_samples);
}
void rs_stretch_flush(void *s, float *const *outputs, int output_samples) {
	static_cast<Stretch *>(s)->flush(outputs, output_samples);
}

}
