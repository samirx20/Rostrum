"""Export Open-Unmix UMX-HQ (MIT weights, Zenodo 3370489) to one ONNX graph: the four target networks on a
magnitude spectrogram. STFT, Wiener filtering and the inverse STFT run in numpy (rostrum_sound/cleanup/spectra.py).
Run in a scratch venv with torch (CPU) + openunmix:  python export_umxhq.py <out.onnx>
"""
import sys

import openunmix
import torch


def traceable_forward(self, x):
    """OpenUnmix.forward, same maths, with shapes read so the export keeps the frame count dynamic (upstream reads
    `x.data.shape`, which the tracer bakes in as constants). Input / output [1, 2, bins, frames]."""
    x = x.permute(3, 0, 1, 2)
    mix = x
    x = x[..., : self.nb_bins]
    x = (x + self.input_mean) * self.input_scale
    x = self.bn1(self.fc1(x.reshape(-1, 2 * self.nb_bins)))
    x = torch.tanh(x.reshape(-1, 1, self.hidden_size))
    x = torch.cat([x, self.lstm(x)[0]], -1)
    x = torch.relu(self.bn2(self.fc2(x.reshape(-1, x.shape[-1]))))
    x = self.bn3(self.fc3(x)).reshape(-1, 1, 2, self.nb_output_bins)
    x = torch.relu(x * self.output_scale + self.output_mean) * mix
    return x.permute(1, 2, 3, 0)


class Four(torch.nn.Module):
    def __init__(self, sep):
        super().__init__()
        self.names = list(sep.target_models.keys())
        self.nets = torch.nn.ModuleList(sep.target_models.values())

    def forward(self, mag):                                   # [1, 2, 2049, frames]
        return torch.stack([traceable_forward(n, mag) for n in self.nets])   # [4, 1, 2, 2049, frames]


sep = openunmix.umxhq(device="cpu").eval()
four = Four(sep).eval()
print("targets:", four.names)
with torch.no_grad():
    t = torch.rand(1, 2, 2049, 50)
    for name, net in sep.target_models.items():
        print(name, "patched vs upstream, max |diff|:", float((traceable_forward(net, t) - net(t)).abs().max()))
torch.onnx.export(four, (torch.rand(1, 2, 2049, 64),), sys.argv[1], input_names=["mag"], output_names=["stems"],
                  opset_version=17, dynamic_axes={"mag": {3: "frames"}, "stems": {4: "frames"}}, dynamo=False)
print("written", sys.argv[1])
