""" $lic$
Copyright (C) 2016-2017 by The Board of Trustees of Stanford University

This program is free software: you can redistribute it and/or modify it under
the terms of the Modified BSD-3 License as published by the Open Source
Initiative.

If you use this program in your research, we request that you reference the
TETRIS paper ("TETRIS: Scalable and Efficient Neural Network Acceleration with
3D Memory", in ASPLOS'17. April, 2017), and that you send us a citation of your
work.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the BSD-3 License for more details.

You should have received a copy of the Modified BSD-3 License along with this
program. If not, see <https://opensource.org/licenses/BSD-3-Clause>.
"""

import itertools

from nn_dataflow.core import NodeRegion
from nn_dataflow.core import PhyDim2
from nn_dataflow.core import PipelineSegment

from . import TestPipelineFixture

class TestPipelineSegment(TestPipelineFixture):
    ''' Tests for PipelineSegment. '''

    def test_valid_args(self):
        ''' Valid arguments. '''
        segment = PipelineSegment((('0',), ('1', '1p')),
                                  self.net['net1'], self.batch_size,
                                  self.resource)
        self.assertTrue(segment.valid)
        self.assertTupleEqual(segment.seg, (('0',), ('1', '1p')))
        self.assertIs(segment.network, self.net['net1'])
        self.assertEqual(segment.batch_size, self.batch_size)
        self.assertIs(segment.resource, self.resource)

    def test_invalid_seg(self):
        ''' Invalid seg. '''
        with self.assertRaisesRegexp(TypeError,
                                     'PipelineSegment: .*seg.*tuple.*'):
            _ = PipelineSegment([('0',), ('1', '1p')],
                                self.net['net1'], self.batch_size,
                                self.resource)

        with self.assertRaisesRegexp(TypeError,
                                     'PipelineSegment: .*seg.*sub-tuple.*'):
            _ = PipelineSegment(('0', '1', '1p'),
                                self.net['net1'], self.batch_size,
                                self.resource)

    def test_invalid_network(self):
        ''' Invalid network. '''
        with self.assertRaisesRegexp(TypeError,
                                     'PipelineSegment: .*network.*'):
            _ = PipelineSegment((('0',), ('1', '1p')),
                                self.net['net1'].input_layer(), self.batch_size,
                                self.resource)

    def test_invalid_resource(self):
        ''' Invalid resource. '''
        with self.assertRaisesRegexp(TypeError,
                                     'PipelineSegment: .*resource.*'):
            _ = PipelineSegment((('0',), ('1', '1p')),
                                self.net['net1'], self.batch_size,
                                PhyDim2(1, 1))

    def test_init_deps_not_valid(self):
        ''' Not valid segment due to init deps. '''

        # Not utilize local data.
        segment = self._make_segment((0, 1), self.net['net3'], temporal=True)
        self.assertFalse(segment.valid)
        self.assertFalse(hasattr(segment, 'alloc'))

        # Local data not available.
        segment = self._make_segment((10, 11, 12), self.net['net5'],
                                     temporal=True)
        self.assertFalse(segment.valid)
        self.assertFalse(hasattr(segment, 'alloc'))

    def test_alloc_not_valid(self):
        ''' Not valid segment due to alloc. '''

        segment = self._make_segment((0, 1), self.net['net1'],
                                     max_util_drop=0.01)
        self.assertFalse(segment.valid)

    def test_as_sequence(self):
        ''' As a sequence. '''
        segment = self._make_segment((0, 1), self.net['net1'])
        self.assertTrue(segment.valid)

        self.assertSequenceEqual(segment, segment.seg)
        self.assertTupleEqual(tuple(segment), segment.seg)

        for ltpl in segment:
            for layer in ltpl:
                self.assertIn(layer, self.net['net1'])

    def test_equal(self):
        ''' Equality. '''
        seg1 = self._make_segment((0, 1), self.net['net1'], max_util_drop=0.1)
        seg2 = self._make_segment((0, 1), self.net['net1'], max_util_drop=0.01)
        seg3 = self._make_segment((0, 1), self.net['net1'], temporal=True)
        self.assertNotEqual(seg1, seg2)
        self.assertNotEqual(seg1, seg3)

        seg4 = self._make_segment((0, 1), self.net['net1'], max_util_drop=0.1)
        self.assertEqual(seg1, seg4)

        net = self.net['net1']
        self.assertSetEqual(set(self._gen_all_segment(net)),
                            set(itertools.chain(self._gen_all_segment(net),
                                                self._gen_all_segment(net))))

    def test_repr(self):
        ''' __repr__. '''
        seg = self._make_segment((0, 1), self.net['net1'], max_util_drop=0.1)
        str_ = repr(seg)
        self.assertIn(repr(seg.seg), str_)
        self.assertIn(repr(seg.resource), str_)
        self.assertIn(repr(seg.max_util_drop), str_)

    def test_alloc_proc(self):
        ''' _alloc_proc. '''
        # pylint: disable=protected-access

        net = self.net['net1']
        self.assertListEqual([net[l].total_ops() for l in net],
                             [200, 600, 30, 1200, 2000])

        ilp = self._make_ilp(net)

        # Single vertex.

        for idx in range(len(ilp.dag_vertex_list)):
            segment = self._make_segment((idx,), ilp.network)
            psr = segment._alloc_proc()

            self.assertEqual(len(psr), 1)
            self.assertTupleEqual(psr[0].origin, (0, 0))
            self.assertTupleEqual(psr[0].dim, self.resource.proc_region.dim)
            self.assertEqual(psr[0].type, NodeRegion.PROC)

        # Multiple vertices.

        psr = self._make_segment((0, 1), net)._alloc_proc()
        nodes = [nr.dim.size() for nr in psr]
        self.assertListEqual(nodes, [16, 48])

        psr = self._make_segment((2, 3), net)._alloc_proc()
        nodes = [nr.dim.size() for nr in psr]
        self.assertListEqual(nodes, [24, 40])

        psr = self._make_segment((1, 2), net)._alloc_proc()
        nodes = [nr.dim.size() for nr in psr]
        self.assertTrue(nodes == [24, 40] or nodes == [22, 42])

        psr = self._make_segment((1, 2, 3), net)._alloc_proc()
        nodes = [nr.dim.size() for nr in psr]
        self.assertTrue(nodes == [12, 20, 32] or nodes == [10, 20, 34])

        # All segments.

        def _check_all_segment(ilp):
            for vseg in ilp._gen_vseg():
                segment = self._make_segment(vseg, ilp.network)
                psr = segment._alloc_proc()
                if psr is None:
                    continue

                # Utilization.
                nodes = [nr.dim.size() for nr in psr]
                ops = [sum(ilp.network[l].total_ops() for l in ltpl)
                       for ltpl in segment]
                self.assertEqual(len(nodes), len(ops))
                time = max(o * 1. / n for o, n in zip(ops, nodes))
                max_ops = time * sum(nodes)
                real_ops = sum(ops)
                self.assertGreaterEqual(real_ops / max_ops, 0.9)

        _check_all_segment(ilp)

        for net_name in ['zfnet', 'net3']:
            net = self.net[net_name]
            ilp = self._make_ilp(net)
            _check_all_segment(ilp)

    def test_allocation(self):
        ''' allocation(). '''

        # Single vertex.

        net = self.net['net1']
        ilp = self._make_ilp(net)
        for idx in range(len(ilp.dag_vertex_list)):
            segment = self._make_segment((idx,), ilp.network)
            alloc = segment.allocation()
            self.assertIsNotNone(alloc)
            self._validate_allocation(segment, alloc)

        # Linear networks.

        for net_name in ['net1', 'net2']:

            net = self.net[net_name]

            for segment in self._gen_all_segment(net):

                alloc = segment.allocation()
                if alloc is None:
                    continue

                self._validate_allocation(segment, alloc)

                # This is a linear network structure.
                rlist = sum(alloc, tuple())

                # The data source of all layers except for the first in the
                # segment should be previous processing regions.
                for r in rlist[1:]:
                    self.assertEqual(r.src_data_region.type, NodeRegion.PROC,
                                     'test_segment_allocation: '
                                     'data source should be PROC region.')

                # The data destination of all layers except for the last in the
                # segment should be local.
                for r in rlist[:-1]:
                    self.assertEqual(r.dst_data_region.type, NodeRegion.PROC,
                                     'test_segment_allocation: '
                                     'data destination should be PROC region.')

        # Complex networks.

        for net_name in ['net3', 'net4', 'net5']:

            net = self.net[net_name]

            for segment in self._gen_all_segment(net):

                alloc = segment.allocation()
                if alloc is None:
                    continue

                self._validate_allocation(segment, alloc)

        # Real networks.

        for net_name in self.net:

            if net_name.startswith('net'):
                continue
            net = self.net[net_name]

            for segment in self._gen_all_segment(net):

                alloc = segment.allocation()
                if alloc is None:
                    continue

                self._validate_allocation(segment, alloc)

    def test_allocation_temp(self):
        ''' allocation() temporal. '''

        for net in self.net.values():

            for segment in self._gen_all_segment(net, temporal=True):

                alloc = segment.allocation()
                if alloc is None:
                    continue

                self._validate_allocation(segment, alloc)

    def test_allocation_invalid(self):
        ''' allocation() for invalid segment. '''
        segment = self._make_segment((0, 1), self.net['net3'], temporal=True)
        self.assertFalse(segment.valid)
        self.assertIsNone(segment.allocation())

    def test_gen_constraint(self):
        ''' gen_constraint(). '''

        # Single vertex.

        for net_name in self.net:

            net = self.net[net_name]
            ilp = self._make_ilp(net)

            for idx in range(len(ilp.dag_vertex_list)):
                segment = self._make_segment((idx,), ilp.network)
                self.assertTrue(segment.valid)

                for constraint, _ in segment.gen_constraint():
                    self._validate_constraint(segment, constraint)

                    # No top loop constraint for single-layer segment.
                    if len(constraint) == 1 and len(constraint[0]) == 1:
                        for c in itertools.chain.from_iterable(constraint):
                            self.assertTrue(c.topifm == 0 and c.topofm == 0
                                            and c.topbat == 0)

        # Spatial pipelining.

        for net_name in self.net:

            if not net_name.startswith('net') and net_name != 'zfnet':
                continue

            net = self.net[net_name]

            for segment in self._gen_all_segment(net):
                if not segment.valid:
                    continue

                for constraint, _ in segment.gen_constraint():
                    self._validate_constraint(segment, constraint)

        # Special cases.

        net = self.net['net2']

        segment = PipelineSegment((('0', '1'), ('2', '3')), net,
                                  self.batch_size, self.resource)

        for constraint, _ in segment.gen_constraint():
            self._validate_constraint(segment, constraint)

    def test_gen_constraint_temporal(self):
        ''' gen_constraint() temporal. '''

        for net_name in self.net:

            net = self.net[net_name]

            for segment in self._gen_all_segment(net, temporal=True):
                if not segment.valid:
                    continue

                for constraint, _ in segment.gen_constraint():
                    self._validate_constraint(segment, constraint)

                    # Single spatial scheduling in temporal pipelining do not
                    # require top BAT loop.
                    for ctpl in constraint:
                        for c in ctpl:
                            self.assertEqual(c.topbat, 0)

