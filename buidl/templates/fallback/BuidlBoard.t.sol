// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {BuidlBoard} from "../src/BuidlBoard.sol";

contract BuidlBoardTest is Test {
    BuidlBoard board;
    address alice = makeAddr("alice");
    address bob = makeAddr("bob");

    function setUp() public {
        board = new BuidlBoard();
    }

    function test_SubmitAndRead() public {
        vm.prank(alice);
        uint256 id = board.submit("demo", "ipfs://cid");
        assertEq(id, 0);
        assertEq(board.entryCount(), 1);
        BuidlBoard.Entry memory e = board.getEntry(0);
        assertEq(e.author, alice);
        assertEq(e.title, "demo");
    }

    function test_EndorseOncePerAddress() public {
        vm.prank(alice);
        board.submit("demo", "");
        vm.prank(bob);
        board.endorse(0);
        assertEq(board.getEntry(0).endorsements, 1);
        vm.prank(bob);
        vm.expectRevert(abi.encodeWithSelector(BuidlBoard.AlreadyEndorsed.selector, 0, bob));
        board.endorse(0);
    }

    function test_RevertSelfEndorse() public {
        vm.startPrank(alice);
        board.submit("demo", "");
        vm.expectRevert(BuidlBoard.SelfEndorsement.selector);
        board.endorse(0);
        vm.stopPrank();
    }

    function test_RevertEmptyTitleAndUnknown() public {
        vm.expectRevert(BuidlBoard.EmptyTitle.selector);
        board.submit("", "");
        vm.expectRevert(abi.encodeWithSelector(BuidlBoard.UnknownEntry.selector, 7));
        board.endorse(7);
    }

    function test_OnlyOwnerCompletesMilestones() public {
        board.submit("demo", "");
        board.completeMilestone(0, "M1 shipped");
        assertEq(board.getEntry(0).milestonesDone, 1);
        vm.prank(bob);
        vm.expectRevert();
        board.completeMilestone(0, "nope");
    }
}
